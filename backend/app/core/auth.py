from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str


async def get_current_user() -> AuthenticatedUser:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication provider is not configured; user-scoped data is unavailable.",
    )


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
