"""
Custom exception types for Council News Bot.

Provides structured error handling across the application.
"""


class CouncilBotException(Exception):
    """Base exception for all Council News Bot errors."""

    pass


class ScrapeError(CouncilBotException):
    """Raised when scraping a council's news fails."""

    pass


class ProxyError(ScrapeError):
    """Raised when proxy connection or authentication fails."""

    pass


class ConfigurationError(CouncilBotException):
    """Raised when configuration is invalid or missing."""

    pass


class StateNotFoundError(ConfigurationError):
    """Raised when requested state configuration doesn't exist."""

    pass


class CouncilNotFoundError(ConfigurationError):
    """Raised when requested council doesn't exist in state."""

    pass


class DatabaseError(CouncilBotException):
    """Raised when database operations fail."""

    pass


class ArticleValidationError(CouncilBotException):
    """Raised when article data fails validation."""

    pass


class PublicationError(CouncilBotException):
    """Raised when publishing to BlueSky/Discord fails."""

    pass


class TimeZoneError(CouncilBotException):
    """Raised when timezone conversion or handling fails."""

    pass
