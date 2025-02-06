"""Exceptions for common errors."""


class UninitializedAccountError(Exception):
    """Thrown when an account has not been initialized, but the user wants to load data."""


class HTMLParseError(Exception):
    """Thrown when parsing the HTML from a response fails."""


class StudentNotFoundError(Exception):
    """Thrown when a student is not found in a course."""
