from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.user.domain.errors import (
    EmailAlreadyRegisteredError,
    InvalidDisplayNameError,
    InvalidEmailError,
    UserNotFoundError,
)
from app.shared.domain.errors import DomainError

ERROR_RESPONSES: dict[type[DomainError], tuple[int, str, str]] = {
    InvalidEmailError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid email", ""),
    InvalidDisplayNameError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid display name", ""),
    EmailAlreadyRegisteredError: (
        status.HTTP_409_CONFLICT,
        "Email already registered",
        "A user with this email already exists.",
    ),
    UserNotFoundError: (
        status.HTTP_404_NOT_FOUND,
        "User not found",
        "The requested user was not found.",
    ),
}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    domain_error = cast(DomainError, exc)
    status_code, title, safe_detail = ERROR_RESPONSES.get(
        type(domain_error),
        (status.HTTP_400_BAD_REQUEST, "Business rule violation", "The request was rejected."),
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"urn:problem:{domain_error.code}",
            "title": title,
            "status": status_code,
            "detail": safe_detail or str(domain_error),
            "instance": request.url.path,
        },
        media_type="application/problem+json",
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
