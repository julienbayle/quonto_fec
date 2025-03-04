from typing import NamedTuple, List
from datetime import datetime
from .journal import Journal
from .ledger_account import LedgerAccount


class MiscellaneousTransactionEntry(NamedTuple):
    """Represents a miscellanious transaction entry in an accounting transaction."""

    Journal: Journal
    """Journal code (e.g., 'ACH' for purchases, 'VTE' for sales)."""

    Account: LedgerAccount
    """General ledger account number (e.g., '411000' for a customer account)."""

    Debit: int
    """Debit amount, 2 decimal value (1,23 euros is 123)"""

    Credit: int
    """Credit amount, 2 decimal value (1,23 euros is 123)"""


class MiscellaneousTransaction(NamedTuple):
    """Represents a miscellanious transaction in accounting (manual transaction)."""

    EcritureDate: datetime
    """Accounting entry date."""

    EcritureLib: str
    """Label of the accounting entry (e.g., 'Customer invoice n°1234')."""

    PieceRef: str
    """Reference of the supporting document (e.g., invoice number)."""

    PieceDate: datetime
    """Date of the supporting document (invoice, expense report)"""

    Entries: List[MiscellaneousTransactionEntry]
    """ Accounting entries within the transaction """
