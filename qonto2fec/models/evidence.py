from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Evidence:
    """Represents a document serving as evidence to validate the legitimacy of an expense or revenue.

    This class holds information about the evidence document's number, source, date and reference
    in the source system, which are used for traceability and audit purposes in accounting systems.
    """

    number: int
    """Continuous counter for the evidence number, ensuring uniqueness and traceability of each document."""

    source: str
    """The location or system where the original evidence document (file or physical) is stored or managed
    (e.g., file server, cloud storage, paper records)."""

    source_reference: str
    """A unique reference identifier for the document within the source system,
    which allows for precise retrieval and verification of the evidence (e.g., file name or database record ID)."""

    source_path: Optional[str]
    """ The path if known of the document in the evidence export directory """

    when: str
    """The date when the evidence was recorded, created or received in the source system (format %Y%m%d)"""

    def _str(self) -> str:
        return f"{self.number:05d}"

    def _asdict(self) -> Dict[str, str]:
        return {
            "number": str(self.number),
            "source": self.source,
            "source_reference": self.source_reference,
            "source_path": self.source_path if self.source_path else "",
            "when": self.when
        }
