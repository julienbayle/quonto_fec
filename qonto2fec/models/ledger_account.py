from typing import List, Dict, Any, Optional


class LedgerAccount:
    """Represents a general ledger account in an accounting system.

    A ledger account is used to track financial transactions related to a specific category,
    such as assets, liabilities, expenses, or revenues.
    """

    code: str
    """The unique account code identifying the ledger account (e.g., '411000' for customer accounts)."""

    name: str
    """The descriptive name of the ledger account (e.g., 'Accounts Receivable')."""

    thirdparty_names_or_quonto_categories: List[str]
    """For a customer or a supprlier : The possible names of the supplier or customer
       For other accounts : The possible transation category or labels in qonto that related to this ledger account
    """

    def __init__(self, code: str, name: str, thirdparty_names_or_quonto_categories: Any = None):
        self.code = code.strip()
        self.name = name.strip()

        if thirdparty_names_or_quonto_categories is None:
            self.thirdparty_names_or_quonto_categories = []
        elif type(thirdparty_names_or_quonto_categories) is List:
            self.thirdparty_names_or_quonto_categories = thirdparty_names_or_quonto_categories
        elif type(thirdparty_names_or_quonto_categories) is str:
            self.thirdparty_names_or_quonto_categories = thirdparty_names_or_quonto_categories.split("|")
        else:
            raise ValueError("Incompatible value type for third party names")

    def _asdict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "thirdparty_names_or_quonto_categories": "|".join(self.thirdparty_names_or_quonto_categories)
        }

    def __str__(self) -> str:
        return str(self.code).ljust(6, '0')

    def fec_compte_num(self) -> str:
        return self.code if self.code[0:3] not in ["401", "411"] else self.code[0:3]

    def fec_compte_lib(self) -> str:
        return self.name

    def fec_compte_aux_num(self) -> Optional[str]:
        return self.code[4:7] if self.code[0:3] in ["401", "411"] else None

    def fec_compte_aux_lib(self) -> Optional[str]:
        if len(self.thirdparty_names_or_quonto_categories) > 0 and self.code[0:3] in ["401", "411"]:
            return self.thirdparty_names_or_quonto_categories[0]
        else:
            return None
