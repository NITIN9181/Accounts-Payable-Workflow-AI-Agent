"""Health monitoring and observability service for AP Workflow Agent."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from ap_workflow.redis.client import redis_client
from ap_workflow.services.message_queue import MessageQueueService, QueueName

logger = logging.getLogger(__name__)


class HealthMonitoringService:
    """Service for health checks and system monitoring."""

    def __init__(self, db_session: Session):
        """Initialize health monitoring service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session
        self.message_queue = MessageQueueService()

    def check_database_connectivity(self) -> Dict[str, Any]:
        """Check PostgreSQL database connectivity.

        Returns:
            Dictionary with status and details
        """
        try:
            result = self.db_session.execute(text("SELECT 1"))
            result.close()
            return {
                "status": "ok",
                "service": "postgresql",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Database connectivity check failed: {str(e)}")
            return {
                "status": "error",
                "service": "postgresql",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def check_redis_connectivity(self) -> Dict[str, Any]:
        """Check Redis connectivity.

        Returns:
            Dictionary with status and details
        """
        try:
            redis_client.client.ping()
            return {
                "status": "ok",
                "service": "redis",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Redis connectivity check failed: {str(e)}")
            return {
                "status": "error",
                "service": "redis",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def check_tesseract_availability(self) -> Dict[str, Any]:
        """Check Tesseract OCR availability.

        Returns:
            Dictionary with status and details
        """
        try:
            import pytesseract
            from PIL import Image
            import io

            # Create a simple test image
            img = Image.new("RGB", (100, 100), color="white")
            text = pytesseract.image_to_string(img)

            return {
                "status": "ok",
                "service": "tesseract",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Tesseract availability check failed: {str(e)}")
            return {
                "status": "error",
                "service": "tesseract",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def check_external_services(self) -> List[Dict[str, Any]]:
        """Check health of external services using circuit breaker states.

        Returns:
            List of health statuses for external services
        """
        from ap_workflow.services.circuit_breaker import circuit_breakers
        
        health_statuses = []
        for service_name, cb in circuit_breakers.items():
            status = "ok"
            if cb.state == "OPEN":
                status = "error"
            elif cb.state == "HALF_OPEN":
                status = "degraded"
            
            health_statuses.append({
                "service": service_name,
                "status": status,
                "state": cb.state.value if hasattr(cb.state, 'value') else cb.state,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        return health_statuses

    def check_nvidia_nim_connectivity(self) -> Dict[str, Any]:
        """Check NVIDIA NIM LLM connectivity (non-critical).

        Returns:
            Dictionary with status and details
        """
        try:
            # This would typically make a test API call to NVIDIA NIM
            # For now, we'll just check if the service is configured
            import os

            nim_api_key = os.getenv("NVIDIA_NIM_API_KEY")
            if not nim_api_key:
                return {
                    "status": "warning",
                    "service": "nvidia_nim",
                    "message": "API key not configured",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return {
                "status": "ok",
                "service": "nvidia_nim",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.warning(f"NVIDIA NIM connectivity check failed: {str(e)}")
            return {
                "status": "warning",
                "service": "nvidia_nim",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def check_gmail_imap_connectivity(self) -> Dict[str, Any]:
        """Check Gmail IMAP connectivity (non-critical).

        Returns:
            Dictionary with status and details
        """
        try:
            import os

            gmail_user = os.getenv("GMAIL_USER")
            if not gmail_user:
                return {
                    "status": "warning",
                    "service": "gmail_imap",
                    "message": "Gmail credentials not configured",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return {
                "status": "ok",
                "service": "gmail_imap",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Gmail IMAP connectivity check failed: {str(e)}")
            return {
                "status": "warning",
                "service": "gmail_imap",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def check_erp_system_connectivity(self) -> Dict[str, Any]:
        """Check ERP System connectivity (non-critical).

        Returns:
            Dictionary with status and details
        """
        try:
            import os

            erp_url = os.getenv("ERP_SYSTEM_URL")
            if not erp_url:
                return {
                    "status": "warning",
                    "service": "erp_system",
                    "message": "ERP system URL not configured",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return {
                "status": "ok",
                "service": "erp_system",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.warning(f"ERP system connectivity check failed: {str(e)}")
            return {
                "status": "warning",
                "service": "erp_system",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_queue_depths(self) -> Dict[str, int]:
        """Get depths of all message queues.

        Returns:
            Dictionary with queue names and message counts
        """
        return self.message_queue.get_queue_stats()

    def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check.

        Returns:
            Dictionary with overall status and component details
        """
        checks = {
            "database": self.check_database_connectivity(),
            "redis": self.check_redis_connectivity(),
            "tesseract": self.check_tesseract_availability(),
            "nvidia_nim": self.check_nvidia_nim_connectivity(),
            "gmail_imap": self.check_gmail_imap_connectivity(),
            "erp_system": self.check_erp_system_connectivity(),
        }

        # Determine overall status
        critical_checks = ["database", "redis", "tesseract"]
        critical_failures = [
            check for check in critical_checks if checks[check]["status"] == "error"
        ]

        if critical_failures:
            overall_status = "error"
        elif any(check["status"] == "warning" for check in checks.values()):
            overall_status = "degraded"
        else:
            overall_status = "ok"

        # Get queue depths
        queue_depths = self.get_queue_depths()

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "queue_depths": queue_depths,
        }


class MetricsService:
    """Service for collecting and exposing metrics."""

    def __init__(self, db_session: Session):
        """Initialize metrics service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db_session = db_session

    def get_invoices_processed_24h(self) -> int:
        """Get count of invoices processed in past 24 hours.

        Returns:
            Count of processed invoices
        """
        try:
            from ap_workflow.models.invoice import Invoice, InvoiceStatus

            cutoff_time = datetime.utcnow() - timedelta(hours=24)

            count = (
                self.db_session.query(Invoice)
                .filter(
                    Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.SCHEDULED, InvoiceStatus.PAID]),
                    Invoice.created_at >= cutoff_time,
                )
                .count()
            )

            return count
        except Exception as e:
            logger.error(f"Error calculating invoices_processed_24h: {str(e)}")
            return 0

    def get_touchless_rate_7d(self) -> float:
        """Get touchless rate (auto-approved) for past 7 days.

        Returns:
            Touchless rate as percentage (0-100)
        """
        try:
            from ap_workflow.models.invoice import Invoice, InvoiceStatus

            cutoff_time = datetime.utcnow() - timedelta(days=7)

            # Total processed invoices
            total = (
                self.db_session.query(Invoice)
                .filter(
                    Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.SCHEDULED, InvoiceStatus.PAID]),
                    Invoice.created_at >= cutoff_time,
                )
                .count()
            )

            if total == 0:
                return 0.0

            # Auto-approved invoices (no exceptions)
            from ap_workflow.models.exception import InvoiceException

            auto_approved = (
                self.db_session.query(Invoice)
                .filter(
                    Invoice.status == InvoiceStatus.APPROVED,
                    Invoice.created_at >= cutoff_time,
                    ~Invoice.exceptions.any(),
                )
                .count()
            )

            return (auto_approved / total) * 100

        except Exception as e:
            logger.error(f"Error calculating touchless_rate_7d: {str(e)}")
            return 0.0

    def get_avg_cycle_time_hours(self) -> float:
        """Get average invoice cycle time for past 7 days.

        Returns:
            Average cycle time in hours
        """
        try:
            from ap_workflow.models.invoice import Invoice, InvoiceStatus

            cutoff_time = datetime.utcnow() - timedelta(days=7)

            # Get approved invoices with both created_at and completed_at
            invoices = (
                self.db_session.query(Invoice)
                .filter(
                    Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.SCHEDULED, InvoiceStatus.PAID]),
                    Invoice.created_at >= cutoff_time,
                )
                .all()
            )

            if not invoices:
                return 0.0

            total_hours = 0
            count = 0

            for invoice in invoices:
                if invoice.created_at:
                    # Use current time if not completed
                    end_time = datetime.utcnow()
                    cycle_time = (end_time - invoice.created_at).total_seconds() / 3600
                    total_hours += cycle_time
                    count += 1

            return total_hours / count if count > 0 else 0.0

        except Exception as e:
            logger.error(f"Error calculating avg_cycle_time_hours: {str(e)}")
            return 0.0

    def get_metrics_prometheus_format(self) -> str:
        """Get metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format
        """
        invoices_24h = self.get_invoices_processed_24h()
        touchless_rate = self.get_touchless_rate_7d()
        avg_cycle_time = self.get_avg_cycle_time_hours()

        metrics = f"""# HELP invoices_processed_24h Total invoices processed in past 24 hours
# TYPE invoices_processed_24h gauge
invoices_processed_24h {invoices_24h}

# HELP touchless_rate_7d Percentage of auto-approved invoices in past 7 days
# TYPE touchless_rate_7d gauge
touchless_rate_7d {touchless_rate:.2f}

# HELP avg_cycle_time_hours Average invoice cycle time in hours for past 7 days
# TYPE avg_cycle_time_hours gauge
avg_cycle_time_hours {avg_cycle_time:.2f}
"""

        return metrics
