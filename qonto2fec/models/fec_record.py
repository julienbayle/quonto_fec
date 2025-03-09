from datetime import datetime, timedelta
from typing import Optional, Dict
from .ledger_account import LedgerAccount
from .evidence import Evidence
from .journal import Journal


class FecRecord:
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

    Montantdevise: Optional[str]
    """Amount in foreign currency (if applicable)."""

    Idevise: Optional[str]
    """Currency code (e.g., 'USD' for US Dollar)."""

    def __init__(self, when: datetime, label: str, journal: Journal, account: LedgerAccount, credit_cent: int, debit_cent: int, ecriture_num: int,
                 evidence: Evidence | None = None, ecriture_rec: str | None = None) -> None:

        # Compute lettrage datetime (always last open day of the month)
        end_of_month = datetime(when.year, when.month, 1) + timedelta(days=32)
        end_of_month = end_of_month - timedelta(days=end_of_month.day + 1)
        day_of_week = end_of_month.weekday()
        if day_of_week > 4:
            end_of_month -= timedelta(days=(day_of_week-4))

        self.JournalCode = journal.code
        self.JournalLib = journal.label
        self.EcritureNum = str(ecriture_num)
        self.EcritureDate = when.strftime("%Y%m%d")
        self.CompteNum = account.fec_compte_num()
        self.CompteLib = account.fec_compte_lib()
        self.CompAuxNum = account.fec_compte_aux_num()
        self.CompAuxLib = account.fec_compte_aux_lib()
        self.PieceRef = str(evidence.number) if evidence else ""
        self.PieceDate = evidence.when.strftime("%Y%m%d") if evidence else ""
        self.EcritureLib = label
        self.Debit = FecRecord.centToFrenchFecFormat(debit_cent)
        self.Credit = FecRecord.centToFrenchFecFormat(credit_cent)
        self.EcritureLet = ecriture_rec
        self.DateLet = end_of_month.strftime("%Y%m%d") if ecriture_rec else None
        self.ValidDate = datetime(when.year, 12, 31).strftime("%Y%m%d")
        self.Montantdevise = None
        self.Idevise = None

    @staticmethod
    def centToFrenchFecFormat(amount: int) -> str:
        if amount <= -100:
            return f"{str(amount)[:-2]},{str(amount)[-2:]}"
        elif -10 <= amount < -100:
            return f"-0,{abs(amount)}"
        elif 0 < amount < 10:
            return f"-0,0{abs(amount)}"
        elif amount == 0:
            return "0,00"
        elif 0 < amount < 10:
            return f"0,0{amount}"
        elif 10 <= amount < 100:
            return f"0,{amount}"
        else:
            return f"{str(amount)[:-2]},{str(amount)[-2:]}"

    @staticmethod
    def frenchFecFormatToCent(amount: str) -> int:
        return int(amount.replace(",", ""))

    def getCreditAsCent(self) -> int:
        return FecRecord.frenchFecFormatToCent(self.Credit)

    def getDebitAsCent(self) -> int:
        return FecRecord.frenchFecFormatToCent(self.Debit)

    def _asdict(self) -> Dict[str, str]:
        return {
            "JournalCode": self.JournalCode,
            "JournalLib": self.JournalLib,
            "EcritureNum": self.EcritureNum,
            "EcritureDate": self.EcritureDate,
            "CompteNum": self.CompteNum,
            "CompteLib": self.CompteLib,
            "CompAuxNum": "" if not self.CompAuxNum else self.CompAuxNum,
            "CompAuxLib": "" if not self.CompAuxLib else self.CompAuxLib,
            "PieceRef": self.PieceRef,
            "PieceDate": self.PieceDate,
            "EcritureLib": self.EcritureLib,
            "Debit": self.Debit,
            "Credit": self.Credit,
            "EcritureLet": "" if not self.EcritureLet else self.EcritureLet,
            "DateLet": "" if not self.DateLet else self.DateLet,
            "ValidDate": self.ValidDate,
            "Montantdevise": "" if not self.Montantdevise else self.Montantdevise,
            "Idevise": "" if not self.Idevise else self.Idevise,
        }
