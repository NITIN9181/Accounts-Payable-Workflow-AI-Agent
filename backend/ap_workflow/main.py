"""Main FastAPI application for AP Workflow Agent."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ap_workflow.core.config import settings
from ap_workflow.database.session import engine, Base
from ap_workflow.models import (
    Invoice,
    InvoiceLineItem,
    OCRExtraction,
    PurchaseOrder,
    POLineItem,
    Receipt,
    ReceiptLineItem,
    MatchingResult,
    DuplicateDetection,
    AnomalyDetection,
    InvoiceException,
    Approval,
    Payment,
    PaymentBatch,
    AuditLog,
    VendorBaseline,
    LLMExplanationCache,
    LLMRequest,
)
from ap_workflow.redis.client import redis_client
from ap_workflow.routes import invoices, exceptions, approvals, health, vendors, websocket, auth, payments
from ap_workflow.routes import settings as settings_router
from ap_workflow.core.logging_config import setup_structured_logging


#changes

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Initialize structured logging
    setup_structured_logging()
    
    # Startup
    print("Starting AP Workflow Agent...")
    
    # Create all database tables with graceful error handling
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created/verified")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
        print("Application will continue without database. Some features may be unavailable.")
    
    # Test Redis connection
    try:
        if redis_client.client:
            redis_client.client.ping()
            print("Redis connection established")
        else:
            print("Warning: Redis client not available")
    except Exception as e:
        print(f"Warning: Redis connection failed: {e}")
    
    # Start WebSocket background consumer task
    from ap_workflow.routes.websocket import consume_and_broadcast
    broadcast_task = None
    if redis_client.client:
        broadcast_task = asyncio.create_task(consume_and_broadcast())
        print("WebSocket broadcast consumer started")
    else:
        print("Warning: WebSocket broadcast consumer disabled (Redis unavailable)")

    # Start Vendor Baseline Update background task
    from ap_workflow.services.vendor_baseline import VendorBaselineService
    async def baseline_update_scheduler():
        while True:
            try:
                print("Running scheduled vendor baseline update...")
                service = VendorBaselineService()
                # Get all vendors that have baselines
                baselines = service.db.query(VendorBaseline).all()
                for b in baselines:
                    service.update_vendor_baseline(b.vendor_key)
                print(f"Successfully updated {len(baselines)} vendor baselines")
            except Exception as e:
                print(f"Error during scheduled baseline update: {e}")
            
            # Wait for 6 hours
            await asyncio.sleep(6 * 3600)

    baseline_task = asyncio.create_task(baseline_update_scheduler())
    print("Vendor baseline update scheduler started")
    
    yield
    
    # Shutdown
    print("Shutting down AP Workflow Agent...")
    if broadcast_task:
        broadcast_task.cancel()
    baseline_task.cancel()
    try:
        await asyncio.gather(broadcast_task, baseline_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    redis_client.close()
    print("Redis connection closed")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Intelligent invoice processing system with OCR, matching, anomaly detection, and approval workflows",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(invoices.router)
app.include_router(exceptions.router)
app.include_router(approvals.router)
app.include_router(health.router)
app.include_router(vendors.router)
app.include_router(websocket.router)
app.include_router(auth.router)
app.include_router(payments.router)
app.include_router(settings_router.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
    
    # Check database connectivity
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        health_status["database"] = "ok"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Redis connectivity
    try:
        redis_client.client.ping()
        health_status["redis"] = "ok"
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    status_code = 200 if health_status["status"] == "ok" else 503
    return JSONResponse(content=health_status, status_code=status_code)


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Metrics endpoint in Prometheus format."""
    # TODO: Implement metrics collection
    return {
        "invoices_processed_24h": 0,
        "touchless_rate_7d": 0.0,
        "avg_cycle_time_hours": 0.0,
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AP Workflow Agent API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "ap_workflow.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
