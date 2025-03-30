from typing import List
from datetime import datetime
from .fec_record import FecRecord


SUPPLIER_CREDIT = "SUPPLIER_CREDIT"
SUPPLIER_INVOICE = "SUPPLIER_INVOICE"
CLIENT_INVOICE = "CLIENT_INVOICE"
CLIENT_CREDIT = "CLIENT_CREDIT"


class Invoice:
    """Represents a customer or a supplier invoice or credit note received or sent"""

    source_name: str
    """Source system (where the invoice is recorded) name"""

    source_id: str
    """Id of the invoice in the source system (where the invoice is recorded)"""

    source_attachment_id: str
    """Id of the invoice document in the source system (where the invoice is recorded)"""

    number: str
    """Reference of the invoice (number)"""

    tyoe: str
    """SUPPLIER_CREDIT, SUPPLIER_INVOICE, CLIENT_INVOICE, CLIENT_CREDIT"""

    when: datetime
    """Date when the invoice was issued or received"""

    total_amount_cent: int
    """Amount with VAT included of the invoice in cent format (1,23 euros is 123)"""

    amount_excluding_vat_cent: int
    """Amount without VAT included of the invoice in cent format (1,23 euros is 123)"""

    amount_vat_cent: int
    """VAT amount of the invoice in cent format (1,23 euros is 123)"""

    thirdparty_name: str
    """Auxiliary account name (e.g., 'Client Dupont')."""

    fec_record: FecRecord | None = None
    """Associated third party fec record to be reconcialiated when paid"""

    associated_credit: List[str]
    """Associated credit Invoice IDs"""

    def __init__(self, source_name: str, source_id: str, source_attachment_id: str, number: str, type: str,
                 when: datetime, total_amount_cents: int, amount_vat_cent: int, thirdparty_name: str) -> None:

        if type not in [SUPPLIER_CREDIT, SUPPLIER_INVOICE, CLIENT_INVOICE, CLIENT_CREDIT]:
            raise ValueError(f"Invalid invoice type : {type}")

        self.type = type
        self.source_name = source_name
        self.source_id = source_id
        self.source_attachment_id = source_attachment_id
        self.number = number
        self.when = when
        self.total_amount_cent = total_amount_cents
        self.amount_excluding_vat_cent = total_amount_cents - amount_vat_cent
        self.amount_vat_cent = amount_vat_cent
        self.thirdparty_name = thirdparty_name
        self.associated_credit = []

    def __str__(self) -> str:
        return str(vars(self))
