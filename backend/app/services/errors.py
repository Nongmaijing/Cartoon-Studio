from __future__ import annotations


class ServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400, code: str = "service_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code

    def as_dict(self) -> dict:
        return {"ok": False, "error": self.message, "code": self.code, "status_code": self.status_code}


class NotFoundError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404, code="not_found")


class ConfirmationRequired(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409, code="confirmation_required")


class ConfigurationError(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503, code="not_configured")
