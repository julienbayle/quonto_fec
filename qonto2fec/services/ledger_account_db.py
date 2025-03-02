import logging
from typing import List, Optional

from ..models.ledger_account import LedgerAccount
from .file_utils import read_dict_from_csv, save_dict_to_csv


class LedgerAccountDB:
    """This class implements a file based ledger account database"""

    accounts: List[LedgerAccount]
    db_name: str

    def __init__(self, db_name: str) -> None:
        self.accounts = [LedgerAccount(**a) for a in read_dict_from_csv(db_name)]
        if len(self.accounts) == 0:
            self.loadDefaultAccounts()

        self.db_name = db_name

    def get_or_create(self, code: str, name: str) -> LedgerAccount:
        if code is None or len(code) < 3:
            raise ValueError(f"Invalid code for a ledger account : {code}")

        # Supplier or customer
        if code[0:3] in ["401", "411"]:
            # Search by full code if provided
            if len(code) == 6:
                existing = self.get_by_code(code)
                if existing:
                    return existing

            # Search by name
            if name is not None or name.strip() != "":
                existing = self.get_by_name(name, code)
                if existing:
                    return existing

            # Create new
            if name is not None and name.strip() != "":
                new_code = int(code[0:3]) * 1000 + len([c for c in self.accounts if c.code[0:3] == code[0:3]]) + 1
                main_account = self.get_by_code(code[0:3])
                if main_account is None:
                    raise ValueError("Missing default account for supplier or customer")
                return self.add(LedgerAccount(str(new_code), main_account.name, name))

        else:
            # Search by code
            existing = self.get_by_code(code)
            if existing:
                return existing

            # Search by name
            if name is not None or name.strip() != "":
                existing = self.get_by_name(name)
                if existing:
                    return existing

            # Create new
            if name is None or name.strip() != "":
                return self.add(LedgerAccount(code, name))

        raise ValueError("Name is mandatory to create a new ledger account")

    def add(self, account: LedgerAccount) -> LedgerAccount:
        logging.getLogger().info(f"New ledger account created {account.code} - {account.name}")
        self.accounts.append(account)
        return account

    def get_by_code(self, code: str) -> Optional[LedgerAccount]:
        for account in self.accounts:
            if account.code == code:
                return account

        return None

    def get_by_name(self, name: str, code: str = "") -> Optional[LedgerAccount]:
        # Supplier or customer
        if code[0:3] in ["401", "411"]:
            for account in self.accounts:
                if account.code[0:3] == code[0:3] and name in account.thirdparty_names_or_quonto_categories:
                    return account
        else:
            for account in self.accounts:
                if account.name == name:
                    return account

        return None

    def loadDefaultAccounts(self) -> None:
        with open("config/accounting.cfg", "r") as file:
            config_text = file.read()

        account_section = False
        for line in config_text.split("\n"):
            line = line.strip()
            if not line or "**" in line:
                continue
            if line[0:2] == "* ":
                account_section = "Account" in line
            elif account_section:
                parts = [part for part in line.split("\t") if part.strip() != ""]
                print(parts)
                if len(parts) == 2:
                    account = LedgerAccount(parts[0], parts[1])
                    self.accounts.append(account)
                elif len(parts) == 3:
                    account = LedgerAccount(parts[0], parts[1], parts[2])
                    self.accounts.append(account)
                else:
                    ValueError(f"Incorrect line in accounting_plan.cfg file : {line}")

    def save(self) -> None:
        save_dict_to_csv([a._asdict() for a in self.accounts], self.db_name, False)
