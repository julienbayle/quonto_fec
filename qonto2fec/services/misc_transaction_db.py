import logging
import re
import pytz
from datetime import datetime
from typing import Dict, List, Optional
from ..models.misc_transaction import MiscellaneousTransaction, MiscellaneousTransactionEntry
from .journal_db import JournalDB
from .ledger_account_db import LedgerAccountDB


class MiscellaneousTransactionDB:
    """Loads and stores miscellaneous transactions from a data file."""

    transactions: Dict[datetime, List[MiscellaneousTransaction]] = {}
    journal_db: JournalDB
    accounts_db: LedgerAccountDB
    previous_date: datetime | None = None

    def __init__(self, filepath: str, journal_db: JournalDB, accounts_db: LedgerAccountDB) -> None:
        """Initialize and load transactions from the given file path."""

        self.journal_db = journal_db
        self.accounts_db = accounts_db

        with open(filepath, "r", encoding="utf-8") as file:
            data_text = file.read()

        self._parse_data(data_text)
        logging.info(f"{len(self.transactions)} miscellaneous transactions retrieved from {filepath}")

    def _parse_data(self, data_text: str) -> None:
        """Parses the raw text data and populates transactions."""
        lines = data_text.split("\n")
        current_transaction = None
        ecriture_lib = None
        ecriture_date = None
        entries = []

        for linenum, line in enumerate(lines):
            line = line.strip()
            linenum += 1  # enumerate starts at 0

            if not line or line.startswith("**"):  # Ignore comments and empty lines
                continue

            if line.startswith("=="):  # Transaction header
                if current_transaction:
                    # Save the previous transaction
                    self._store_transaction(current_transaction, entries)
                    current_transaction = None
                    ecriture_lib = None
                    ecriture_date = None
                    entries = []  # Reset operations for the new transaction

                line = re.sub('[\t]+', '\t', line.replace("==", ""))
                parts = line.strip().split("\t")

                if len(parts) == 1 and not ecriture_lib:  # First line: transaction label
                    ecriture_lib = parts[0].strip()

                elif len(parts) == 1 and ecriture_lib and not ecriture_date:  # Second line: EcritureDate
                    ecriture_date_txt = parts[0].strip()
                    try:
                        ecriture_date = datetime.strptime(ecriture_date_txt, "%d/%m/%Y")
                        local_tz = pytz.timezone("Europe/Paris")
                        utc_tz = pytz.timezone("UTC")
                        dt_utc = utc_tz.localize(ecriture_date)
                        ecriture_date_local = local_tz.normalize(dt_utc)
                    except Exception as e:
                        raise ValueError(f"Unexpected date format at line {linenum} : {line}") from e

                else:  # Third line: PieceRef, PieceDate
                    if len(parts) == 2:
                        piece_ref = parts[0]

                        piece_date_txt = parts[1]
                        try:
                            piece_date = datetime.strptime(piece_date_txt, "%d/%m/%Y")
                        except Exception as e:
                            raise ValueError(f"Unexpected date format at line {linenum} : {parts}") from e

                        if not ecriture_date or not ecriture_lib:
                            raise ValueError(f"Unexpected content at line {linenum}, missing EcritureLib : {parts}")

                        current_transaction = MiscellaneousTransaction(
                            EcritureDate=ecriture_date_local,
                            EcritureLib=ecriture_lib,
                            PieceRef=piece_ref,
                            PieceDate=piece_date,
                            Entries=[]
                        )
                    else:
                        raise ValueError(f"Unexpected content at line {linenum} : {parts}")

            else:  # Operation line
                parts = line.split()
                if len(parts) == 4:
                    journal = self.journal_db.get_by_code(parts[0])
                    if not journal:
                        raise ValueError(f"Unexpected journal code at line {linenum} : {parts}")

                    account = self.accounts_db.get_by_code(parts[1])
                    if not account:
                        raise ValueError(f"Unexpected account code at line {linenum} : {parts}")

                    # Validate number format
                    try:
                        debit = int(float(parts[2].replace(".", ",")) * 100)
                        credit = int(float(parts[3].replace(".", ",")) * 100)
                    except Exception as e:
                        raise ValueError(f"Unexpected amount format at line {linenum} : {parts}") from e

                    entries.append(MiscellaneousTransactionEntry(
                        Journal=journal,
                        Account=account,
                        Credit=credit,
                        Debit=debit,
                    ))
                else:
                    raise ValueError(f"Unexpected content at line {linenum} : {parts}")

        # Save the last transaction
        if current_transaction:
            self._store_transaction(current_transaction, entries)

    def _store_transaction(self, transaction: MiscellaneousTransaction, entries: List[MiscellaneousTransactionEntry]) -> None:
        """Stores a transaction in the dictionary using EcritureDate as the key."""
        if not entries:
            return  # Ignore transactions without operations

        full_transaction = MiscellaneousTransaction(
            EcritureDate=transaction.EcritureDate,
            EcritureLib=transaction.EcritureLib,
            PieceRef=transaction.PieceRef,
            PieceDate=transaction.PieceDate,
            Entries=entries
        )

        if transaction.EcritureDate in self.transactions:
            self.transactions[transaction.EcritureDate].append(full_transaction)
        else:
            self.transactions[transaction.EcritureDate] = [full_transaction]

    def getUntil(self, until_date: Optional[datetime]) -> List[MiscellaneousTransaction]:
        """
        Retrieves all non already retrieved transactions until a date (or all remaining if until_date is None)
        """

        result = []
        for transaction_date, transactions in self.transactions.items():
            if (not self.previous_date or self.previous_date < transaction_date) and (not until_date or transaction_date <= until_date):
                result.extend(transactions)

        self.previous_date = until_date
        return result
