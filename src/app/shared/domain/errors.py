class DomainError(Exception):
    """Base class for expected business rule failures."""

    code = "domain_error"
