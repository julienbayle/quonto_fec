from datetime import datetime, timedelta
from typing import NamedTuple, Optional, List
from .ledger_account import LedgerAccount
from .evidence import Evidence
from .journal import Journal


class FecRecord(NamedTuple):
    """Represents a line in the French FEC (Fichier des Écritures Comptables) file."""

    JournalCode: str
    """Journal code (e.g., 'ACH' for purchases, 'VTE' for sales)."""

    JournalLib: str
    """Journal label (e.g., 'Purchases', 'Sales')."""

    EcritureNum: str
    """Unique accounting entry number ensuring traceability."""

    EcritureDate: str
    """Accounting entry date in 'YYYYMMDD' format."""

    CompteNum: str
    """General ledger account number (e.g., '411000' for a customer account)."""

    CompteLib: str
    """General ledger account label (e.g., 'Customers')."""

    CompAuxNum: Optional[str]
    """Auxiliary account number, used for third parties (customers, suppliers)."""

    CompAuxLib: Optional[str]
    """Auxiliary account label (e.g., 'Client Dupont')."""

    PieceRef: str
    """Reference of the supporting document (e.g., invoice number)."""

    PieceDate: str
    """Date of the supporting document (invoice, expense report) in 'YYYYMMDD' format."""

    EcritureLib: str
    """Label of the accounting entry (e.g., 'Customer invoice n°1234')."""

    Debit: str
    """Debit amount, formatted in French style ('1000,00')."""

    Credit: str
    """Credit amount, formatted in French style ('1000,00')."""

    EcritureLet: Optional[str]
    """Matching code to link related accounting entries (e.g., 'A123')."""

    DateLet: Optional[str]
    """Matching date in 'YYYYMMDD' format, if the entry is matched."""

    ValidDate: str
    """Accounting validation date in 'YYYYMMDD' format."""

    Montantdevise: Optional[float]
    """Amount in foreign currency (if applicable)."""

    Idevise: Optional[str]
    """Currency code (e.g., 'USD' for US Dollar)."""


def create(when: datetime, label: str, journal: Journal, account: LedgerAccount, credit: int, debit: int, ecriture_num: int,
           evidences: List[Evidence] | None = None, ecriture_rec: str | None = None) -> FecRecord:

    # Compute lettrage datetime (always last open day of the month)
    end_of_month = datetime(when.year, when.month, 1) + timedelta(days=32)
    end_of_month = end_of_month - timedelta(days=end_of_month.day + 1)
    day_of_week = end_of_month.weekday()
    if day_of_week > 4:
        end_of_month -= timedelta(days=(day_of_week-4))

    return FecRecord(
        JournalCode=journal.code,
        JournalLib=journal.label,
        EcritureNum=str(ecriture_num),
        EcritureDate=when.strftime("%Y%m%d"),
        CompteNum=account.fec_compte_num(),
        CompteLib=account.fec_compte_lib(),
        CompAuxNum=account.fec_compte_aux_num(),
        CompAuxLib=account.fec_compte_aux_lib(),
        PieceRef=",".join([str(evidence.number) for evidence in evidences]) if evidences is not None and len(evidences) > 0 else "",
        PieceDate=when.strftime("%Y%m%d"),
        EcritureLib=label,
        Debit=f"{debit/100.0:.2f}".replace(".", ","),
        Credit=f"{credit/100.0:.2f}".replace(".", ","),
        EcritureLet=ecriture_rec,
        DateLet=end_of_month.strftime("%Y%m%d") if ecriture_rec else None,
        ValidDate=end_of_month.strftime("%Y%m%d"),
        Montantdevise=None,
        Idevise=None,
    )
