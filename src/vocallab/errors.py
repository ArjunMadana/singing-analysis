class VocalLabError(Exception):
    """An expected error with an operator-actionable message."""


class DependencyError(VocalLabError):
    """A required local executable or Python dependency is unavailable."""


class MediaError(VocalLabError):
    """Input media could not be inspected or decoded."""


class AnalysisError(VocalLabError):
    """Analysis could not produce reliable output."""

