from fastapi import HTTPException, status


def api_error(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def unauthenticated(message: str = "Authentication is required.") -> HTTPException:
    return api_error(
        status.HTTP_401_UNAUTHORIZED,
        "UNAUTHENTICATED",
        message,
    )

