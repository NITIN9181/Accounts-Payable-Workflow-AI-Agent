"""FastAPI dependencies (auth, RBAC) for AP Workflow Agent."""

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ap_workflow.core.security import verify_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Dict[str, Any]:
    """Return verified JWT claims from Authorization: Bearer <token>."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")

    try:
        return verify_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def get_current_role(claims: Dict[str, Any] = Depends(get_current_claims)) -> str:
    role = claims.get("role") or ""
    return str(role)


def get_current_user_id(claims: Dict[str, Any] = Depends(get_current_claims)) -> Optional[str]:
    """Return user id (JWT sub) as string."""
    sub = claims.get("sub")
    return str(sub) if sub is not None else None

