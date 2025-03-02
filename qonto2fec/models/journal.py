from typing import NamedTuple


class Journal(NamedTuple):
    """Represents a journal"""

    code: str
    """Journal codification"""

    label: str
    """Full journal label."""

    def _str(self) -> str:
        return f"{self.code} - {self.label}"
