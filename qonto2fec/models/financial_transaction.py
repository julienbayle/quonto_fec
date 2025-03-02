from datetime import datetime
from typing import Any, List
from .fec_record import FecRecord


class FinancialTransaction:
    amount_excluding_vat: int = 0
    """ Net amount - 2 decimal value (1,23 euros is 123) """

    vat: int = 0
    """ Net amount - 2 decimal value (1,23 euros is 123) """

    when: datetime
    """ Operation date """

    attachments: List[str] = []
    """ Evidence pieces references """

    category: str
    """ Transaction category """

    thirdparty_name: str
    """ Supplier or customer name """

    note: str
    """ Manually added note """

    reference: str = ""
    """ Reference """

    operation_type: str
    """ Operation type"""

    fec_records: List[FecRecord] = []
    """ Associated fec records"""

    def __str__(self) -> str:
        return str(vars(self))

    def __init__(self, transaction: Any) -> None:
        """
        Load data from a raw Qonto transaction.
        If any validation problem is encountered, raise a ValueError Exception.
        """
        name = f"{transaction['label']} ({transaction['transaction_id']})"

        if transaction["status"] != "completed":
            raise ValueError(f"{name} : Transaction is not yet completed or have been declined")

        if transaction["currency"] != "EUR":
            raise ValueError(f"{name}: Only EUR currency is supported")

        if (
            transaction["attachment_required"]
            and len(transaction["attachments"]) == 0
            and not transaction["attachment_lost"]
            and transaction["operation_type"] != "qonto_fee"
        ):
            raise ValueError(f"{name}: A required attachment is missing")

        if len(transaction["label_ids"]) > 1:
            raise ValueError(f"{name}: Only one label per transaction is allowed")

        amount = transaction["amount_cents"]
        side = 1 if transaction["side"] == "credit" else -1

        if "vat_details" in transaction is not None and "items" in transaction["vat_details"] and len(transaction["vat_details"]["items"]) > 0:
            amount_excluding_vat = 0.0
            vat = 0.0
            for vat_detail in transaction["vat_details"]["items"]:
                if vat_detail["rate"] not in [0.0, 5.5, 10, 20]:
                    raise ValueError(f"{name}: VAT rate not supported : {vat_detail['rate']}")
                amount_excluding_vat += side * vat_detail["amount_excluding_vat_cents"]
                vat += side * vat_detail["amount_cents"]
        else:
            vat = 0.0
            amount_excluding_vat = side * amount

        if vat + amount_excluding_vat != amount * side:
            raise ValueError(f"{name}: Amount error ! {vat} + {amount_excluding_vat} != {amount * side}")

        if transaction["operation_type"] == "qonto_fee" and (transaction["note"] is None or transaction["note"] == ""):
            transaction["note"] = "Frais bancaires Qonto"

        self.amount_excluding_vat = int(amount_excluding_vat)
        self.vat = int(vat)
        self.when = transaction["settled_at"]
        self.attachments = transaction["attachment_ids"]
        self.category = transaction["category"] if len(transaction["label_ids"]) == 0 else transaction["labels"][0]["name"]
        self.thirdparty_name = transaction["label"]
        self.note = transaction["note"]
        self.reference = transaction["reference"]
        self.operation_type = transaction["operation_type"]
        self.fec_records = []

    def attach_fec_record(self, fec_record: FecRecord) -> None:
        self.fec_records.append(fec_record)
