"""ML Engine custom exceptions."""


class MLEngineError(Exception):
    """Base ML engine error."""


class DatasetError(MLEngineError):
    """Dataset load / parse errors."""


class ValidationError(MLEngineError):
    """Plan validation errors."""


class ModelError(MLEngineError):
    """Model training / prediction errors."""


class SplitError(ValidationError):
    """Split percentage errors."""


class MetricError(ValidationError):
    """Invalid metric for task."""


class LibraryNotInstalledError(MLEngineError):
    """Required library missing."""
