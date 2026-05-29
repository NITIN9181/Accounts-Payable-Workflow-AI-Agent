"""Health check and metrics routes for AP Workflow Agent."""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ap_workflow.database.session import get_db
from ap_workflow.services.health_monitoring import HealthMonitoringService, MetricsService

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/seed-demo-data")
def seed_demo_data_endpoint(db: Session = Depends(get_db)) -> dict:
    """Seed demo data into the database.
    
    Returns:
        Dictionary with seeding status
    """
    try:
        from seed_demo_data import seed_demo_data
        seed_demo_data()
        return {
            "status": "ok",
            "message": "Demo data seeded successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"Error seeding demo data: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Failed to seed demo data: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict:
    """Perform comprehensive health check.

    Returns:
        Dictionary with overall status and component details
    """
    try:
        service = HealthMonitoringService(db)
        return service.perform_health_check()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/health/database")
def health_check_database(db: Session = Depends(get_db)) -> dict:
    """Check database connectivity.

    Returns:
        Dictionary with database status
    """
    try:
        from sqlalchemy import text
        # Try a simple query
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"Database connection error: {e}")
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/health/redis")
def health_check_redis(db: Session = Depends(get_db)) -> dict:
    """Check Redis connectivity.

    Returns:
        Dictionary with Redis status
    """
    try:
        service = HealthMonitoringService(db)
        return service.check_redis_connectivity()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis health check failed: {str(e)}")


@router.get("/health/queues")
def health_check_queues(db: Session = Depends(get_db)) -> dict:
    """Get message queue depths.

    Returns:
        Dictionary with queue names and message counts
    """
    try:
        service = HealthMonitoringService(db)
        queue_depths = service.get_queue_depths()
        return {
            "status": "ok",
            "queue_depths": queue_depths,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Queue health check failed: {str(e)}")


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)) -> str:
    """Get metrics in Prometheus format.

    Returns:
        Metrics in Prometheus text format
    """
    try:
        service = MetricsService(db)
        return service.get_metrics_prometheus_format()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")


@router.get("/metrics/json")
def get_metrics_json(db: Session = Depends(get_db)) -> dict:
    """Get metrics in JSON format.

    Returns:
        Dictionary with metrics
    """
    try:
        service = MetricsService(db)
        return {
            "invoices_processed_24h": service.get_invoices_processed_24h(),
            "touchless_rate_7d": service.get_touchless_rate_7d(),
            "avg_cycle_time_hours": service.get_avg_cycle_time_hours(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")


@router.get("/metrics/dashboard")
def get_dashboard_metrics(db: Session = Depends(get_db)) -> dict:
    """Get dashboard KPI metrics.

    Returns:
        Dictionary with KPI metrics for the dashboard
    """
    try:
        service = MetricsService(db)
        return {
            "invoices_processed_24h": service.get_invoices_processed_24h(),
            "touchless_rate_7d": round(service.get_touchless_rate_7d(), 1),
            "avg_cycle_time_hours": round(service.get_avg_cycle_time_hours(), 1),
            "discount_captured_30d": 0,  # TODO: implement discount tracking
        }
    except Exception as e:
        # Return default metrics instead of 500 error
        print(f"Dashboard metrics retrieval failed: {e}")
        return {
            "invoices_processed_24h": 0,
            "touchless_rate_7d": 0,
            "avg_cycle_time_hours": 0,
            "discount_captured_30d": 0,
        }


@router.get("/metrics/cashflow-forecast")
def get_cashflow_forecast(db: Session = Depends(get_db)) -> list:
    """Get 30-day cash flow forecast data.

    Returns:
        List of daily projected outflow amounts
    """
    try:
        from sqlalchemy import func
        from ap_workflow.models.payment import Payment

        today = datetime.utcnow().date()
        forecast = []

        for i in range(30):
            day = today + timedelta(days=i)
            total = (
                db.query(func.sum(Payment.payment_amount))
                .filter(
                    Payment.scheduled_payment_date == day,
                    Payment.status.in_(["SCHEDULED", "PENDING"])
                )
                .scalar() or 0
            )
            forecast.append({
                "date": day.strftime("%b %d"),
                "amount": float(total),
                "threshold": 50000,
            })

        return forecast
    except Exception as e:
        # Return empty forecast instead of 500 error
        print(f"Cash flow forecast failed: {e}")
        return []

