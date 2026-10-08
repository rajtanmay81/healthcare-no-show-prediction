"""Domain exceptions. Services raise these; ``main.py`` maps them to HTTP responses."""


class AppError(Exception):
    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(f"{resource} with id {identifier} was not found")


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule_violation"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_failed"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class ModelNotAvailableError(AppError):
    status_code = 503
    code = "model_not_available"
