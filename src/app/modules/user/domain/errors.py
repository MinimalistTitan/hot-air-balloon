from app.shared.domain.errors import DomainError


class InvalidEmailError(DomainError):
    code = "invalid_email"


class InvalidDisplayNameError(DomainError):
    code = "invalid_display_name"


class EmailAlreadyRegisteredError(DomainError):
    code = "email_already_registered"


class UserNotFoundError(DomainError):
    code = "user_not_found"
