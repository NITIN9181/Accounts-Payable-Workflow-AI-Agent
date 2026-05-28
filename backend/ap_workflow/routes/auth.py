"""Authentication routes for AP Workflow Agent.

Provides demo-credential login + token refresh + current-user endpoints
matching the frontend contract (POST /api/v1/auth/login,
POST /api/v1/auth/refresh, GET /api/v1/auth/me).

Demo users are hardcoded to mirror the credentials displayed on the
LoginPage. Replace with a real user store before production.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from ap_workflow.core.deps import get_current_claims
from ap_workflow.core.security import create_access_token, verify_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# --- Demo user store -------------------------------------------------------
# Keep in sync with the credentials shown on the LoginPage demo panel.
_DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "clerk@example.com": {
        "id": "user-clerk-001",
        "email": "clerk@example.com",
        "password": "password",
        "role": "AP_CLERK",
        "department": "Accounts Payable",
    },
    "manager@example.com": {
        "id": "user-manager-001",
        "email": "manager@example.com",
        "password": "password",
        "role": "MANAGER",
        "department": "Finance",
    },
    "cfo@example.com": {
        "id": "user-cfo-001",
        "email": "cfo@example.com",
        "password": "password",
        "role": "CFO",
        "department": "Executive",
    },
}


def _public_user(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a User payload without the password field."""
    return {k: v for k, v in record.items() if k != "password"}


def _user_from_claims(claims: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the demo user record referenced by JWT claims."""
    sub = claims.get("sub")
    for record in _DEMO_USERS.values():
        if record["id"] == sub:
            return _public_user(record)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="User not found",
    )


# --- Schemas ---------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    token: str = Field(min_length=1)


class AuthResponse(BaseModel):
    token: str
    user: Dict[str, Any]


class MeResponse(BaseModel):
    user: Dict[str, Any]


# --- Routes ----------------------------------------------------------------
@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    """Authenticate a demo user and return a signed JWT."""
    record = _DEMO_USERS.get(payload.email.lower())
    if record is None or record["password"] != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = _public_user(record)
    token = create_access_token(
        subject=user["id"],
        role=user["role"],
        extra_claims={"email": user["email"]},
    )
    return AuthResponse(token=token, user=user)


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest) -> AuthResponse:
    """Issue a new JWT for an already-valid token."""
    try:
        claims = verify_access_token(payload.token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    user = _user_from_claims(claims)
    token = create_access_token(
        subject=user["id"],
        role=user["role"],
        extra_claims={"email": user["email"]},
    )
    return AuthResponse(token=token, user=user)


@router.get("/me", response_model=MeResponse)
def me(claims: Dict[str, Any] = Depends(get_current_claims)) -> MeResponse:
    """Return the current authenticated user's profile."""
    return MeResponse(user=_user_from_claims(claims))
