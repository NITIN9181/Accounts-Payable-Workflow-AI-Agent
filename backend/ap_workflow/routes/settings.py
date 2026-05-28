"""Settings routes for AP Workflow Agent."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ap_workflow.database.session import get_db

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# In-memory config store (replace with DB-backed config in production)
_workflow_config: dict = {
    "department_threshold": 5000.0,
    "manager_threshold": 25000.0,
    "cfo_threshold": 100000.0,
    "sla_clerk": 4,
    "sla_manager": 24,
    "sla_cfo": 48,
}


@router.get("/workflow")
def get_workflow_config(db: Session = Depends(get_db)) -> dict:
    """Get approval workflow configuration.

    Returns:
        Current workflow configuration
    """
    return _workflow_config


@router.put("/workflow")
def update_workflow_config(updates: dict, db: Session = Depends(get_db)) -> dict:
    """Update approval workflow configuration.

    Args:
        updates: Fields to update

    Returns:
        Updated workflow configuration
    """
    allowed_keys = {
        "department_threshold", "manager_threshold", "cfo_threshold",
        "sla_clerk", "sla_manager", "sla_cfo",
    }
    invalid_keys = set(updates.keys()) - allowed_keys
    if invalid_keys:
        raise HTTPException(status_code=400, detail=f"Unknown config keys: {invalid_keys}")

    _workflow_config.update(updates)
    return _workflow_config
