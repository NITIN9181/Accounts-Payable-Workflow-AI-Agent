"""JWT token creation and validation for AP Workflow Agent."""

from datetime import datetime, timedelta, UTC
from typing import Any, Dict, Optional

from jose import JWTError, jwt

from ap_workflow.core.config import settings

JWT_ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    *,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(hours=settings.jwt_expire_hours)
    )
    payload: Dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if role:
        payload["role"] = role
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def verify_access_token(token: str) -> Dict[str, Any]:
    """Verify JWT access token and return claims.

    Raises:
        ValueError: If token is missing, malformed, invalid, or expired.
    """
    if not token or not token.strip():
        raise ValueError("Token is empty")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise ValueError(f"Token validation failed: {exc}") from exc
