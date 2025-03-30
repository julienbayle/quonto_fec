from typing import NamedTuple


class Evidence(NamedTuple):
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

    when: str
    """The date when the evidence was recorded, created or received in the source system (format %Y%m%d)"""

    def _str(self) -> str:
        return f"{self.number:05d}"
