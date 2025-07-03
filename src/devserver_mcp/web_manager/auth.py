import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def generate_bearer_token() -> str:
    """Generate a secure random bearer token."""
    return secrets.token_urlsafe(32)


def create_token_verifier(bearer_token: str):
    """Create a token verification function with the provided token."""

    async def verify_token(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> None:
        """Verify that the provided bearer token matches the generated token."""
        if not bearer_token or credentials.credentials != bearer_token:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    return verify_token
