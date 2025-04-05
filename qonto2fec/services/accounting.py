import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from tabulate import tabulate
from colorama import Fore, Style

from .evidence_db import EvidenceDB
from .ledger_account_db import LedgerAccountDB
from .journal_db import JournalDB
from .misc_transaction_db import MiscellaneousTransactionDB
from ..models.financial_transaction import FinancialTransaction
from ..models.invoice import Invoice, CLIENT_CREDIT, CLIENT_INVOICE, SUPPLIER_INVOICE
from ..models.fec_record import FecRecord
from .file_utils import save_dict_to_csv
from .date_utils import conv_date_from_utc_to_local


class AccountingService:

    fec_records: List[FecRecord] = []
    fec_counter: int = 0
    reconciliation_counter: int = 0

    journal_db: JournalDB
    evidence_db: EvidenceDB
    leadger_account_db: LedgerAccountDB
    misc_transaction_db: MiscellaneousTransactionDB
    invoices: List[Invoice]

    def __init__(self, siren: str, start_date: str, end_date: str) -> None:
        self.start_date = start_date
        self.end_date = end_date
        self.fec_filename = f"{siren}FEC{str(end_date)}"
        self.invoices = []
        self.invoices_filename = f"{siren}INVOICES{str(end_date)}"

        # Load databases
        self.journal_db = JournalDB()
        self.evidence_db = EvidenceDB(f"{siren}EVIDENCES{str(end_date)}")
        self.leadger_account_db = LedgerAccountDB(f"{siren}ACCOUNTS")

        # Load miscellaneous transactions
        misc_path = f"config/misc_transactions{str(end_date.replace('-', ''))}.txt"
        self.misc_transaction_db = MiscellaneousTransactionDB(misc_path, self.journal_db, self.leadger_account_db)

    def save(self) -> None:
        # Save FEC records
        save_dict_to_csv([r._asdict() for r in self.fec_records], self.fec_filename, False)

        # Save Invoices
        save_dict_to_csv([i._asdict() for i in self.invoices if i.type in [CLIENT_INVOICE, CLIENT_CREDIT]], self.invoices_filename, False)

        # Save evidences database
        self.evidence_db.save()

        # Save ledger accounts database
        self.leadger_account_db.save()

    def addInvoices(self, invoices: List[Invoice]) -> None:
        self.invoices.extend(invoices)

    def _getNextOpCounter(self, when: Optional[datetime]) -> int:
        if when:
            self.doAccountingForMiscTransactionBefore(when)
            self.doAccountingForInvoicesBefore(when)

        self.fec_counter += 1
        return self.fec_counter

    def _getNextReconciliation(self) -> str:
        i1 = self.reconciliation_counter % 26
        i2 = int(self.reconciliation_counter / 26) % 26
        i3 = int(self.reconciliation_counter / 26 / 26) % 26
        rec = f"{chr(i3 + ord('A'))}{chr(i2 + ord('A'))}{chr(i1 + ord('A'))}"
        self.reconciliation_counter += 1
        if i3 > 25:
            raise Exception("Reconciliation limit reached")
        return rec

    def _createFecRecordFromBankTransaction(self, transaction: FinancialTransaction,
                                            journal_code: str, account: str,
                                            credit_cent: int, debit_cent: int, num: int,
                                            rec: str | None = None) -> FecRecord:
        # EcritureLib
        ecritureLib = ""

        if transaction.reference is not None and journal_code != "VE":
            ecritureLib += str(transaction.reference).replace("\n", " ").replace("\t", " ")

        if transaction.note is not None and len(transaction.note) > 0:
            ecritureLib += " - " if len(ecritureLib) > 0 else ""
            ecritureLib += str(transaction.note).replace("\n", " ").replace("\t", " ")

        if len(ecritureLib) == 0:
            raise Exception(f"Empty label for transaction {transaction}")

        evidence = None
        if len(transaction.attachments) > 0:
            evidence = self.evidence_db.get_or_add("Qonto", transaction.attachments[0], transaction.when)

        fecRecord = FecRecord(
            when=transaction.when,
            label=ecritureLib,
            journal=self.journal_db.get_by_code(journal_code),
            account=self.leadger_account_db.get_or_create(account, transaction.thirdparty_name),
            evidence=evidence,
            credit_cent=credit_cent,
            debit_cent=debit_cent,
            ecriture_num=num,
            ecriture_rec=rec
        )
        transaction.attach_fec_record(fecRecord)
        self.fec_records.append(fecRecord)
        return fecRecord

    def doAccountingForBankTransaction(self, transaction: FinancialTransaction) -> None:
        """Apply accounting rules, attach generated FEC records to the transaction
           and append it in fec_records collection
        """

        # Invoice payment
        if "sales" == transaction.category and transaction.amount_excluding_vat > 0:
            num = self._getNextOpCounter(transaction.when)
            rec = self._getNextReconciliation()
            self._createFecRecordFromBankTransaction(transaction, "BQ", "512", 0, transaction.amount_excluding_vat + transaction.vat, num)
            fec = self._createFecRecordFromBankTransaction(transaction, "BQ", "411", transaction.amount_excluding_vat + transaction.vat, 0, num, rec)

            # Search corresponding invoice for reconcialiation and mark VAT to be paid
            invoice_fec_found = False
            for fec_record in self.fec_records:
                amount_match = fec_record.Credit == fec.Debit and fec_record.Debit == fec.Credit
                attachment_match = fec_record.PieceRef in fec.PieceRef or fec_record.EcritureLib in fec.EcritureLib
                if fec.EcritureNum != fec_record.EcritureNum and amount_match and attachment_match:
                    invoice_fec_found = True

                    # Reconciliate invoice
                    fec_record.EcritureLet = fec.EcritureLet
                    fec_record.DateLet = fec.DateLet

                    # Mark TVA to be paid
                    self.fec_records.append(FecRecord(
                        when=transaction.when,
                        label=fec.EcritureLib + " encaissée",
                        journal=self.journal_db.get_by_code('VE'),
                        account=self.leadger_account_db.get_by_code_or_fail('4458'),
                        evidence=None,
                        credit_cent=max(-transaction.vat, 0),
                        debit_cent=max(transaction.vat, 0),
                        ecriture_num=num,
                        ecriture_rec=None
                    ))
                    self.fec_records.append(FecRecord(
                        when=transaction.when,
                        label=fec.EcritureLib + " encaissée",
                        journal=self.journal_db.get_by_code('VE'),
                        account=self.leadger_account_db.get_by_code_or_fail('44571'),
                        evidence=None,
                        credit_cent=max(transaction.vat, 0),
                        debit_cent=max(-transaction.vat, 0),
                        ecriture_num=num,
                        ecriture_rec=None
                    ))

            if not invoice_fec_found:
                raise Exception(f"Invoice not found in accounting : {fec.PieceRef} {fec.EcritureLib} {fec.EcritureDate}")

        # Financial investment (starting)
        elif "treasury_and_interco" == transaction.category and transaction.amount_excluding_vat < 0 and transaction.vat == 0:
            num = self._getNextOpCounter(transaction.when)
            self._createFecRecordFromBankTransaction(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
            self._createFecRecordFromBankTransaction(transaction, "BQ", "580", 0, -transaction.amount_excluding_vat, num)
            num = self._getNextOpCounter(transaction.when)
            self._createFecRecordFromBankTransaction(transaction, "BQ1", "580", -transaction.amount_excluding_vat, 0, num)
            self._createFecRecordFromBankTransaction(transaction, "BQ1", "512001", 0, -transaction.amount_excluding_vat, num)

        # Financial investment (ending)
        elif "treasury_and_interco" == transaction.category and transaction.amount_excluding_vat > 0 and transaction.vat == 0:
            num = self._getNextOpCounter(transaction.when)
            self._createFecRecordFromBankTransaction(transaction, "BQ1", "512001", transaction.amount_excluding_vat, 0, num)
            self._createFecRecordFromBankTransaction(transaction, "BQ1", "580", 0, transaction.amount_excluding_vat, num)
            num = self._getNextOpCounter(transaction.when)
            self._createFecRecordFromBankTransaction(transaction, "BQ", "580", transaction.amount_excluding_vat, 0, num)
            self._createFecRecordFromBankTransaction(transaction, "BQ", "512", 0, transaction.amount_excluding_vat, num)

        # VAT
        elif (
            "TVA" in str(transaction.reference)
            and "CA3" in str(transaction.reference)
            and "DGFIP" in transaction.thirdparty_name
            and transaction.amount_excluding_vat < 0
            and transaction.vat == 0
        ):
            num = self._getNextOpCounter(transaction.when)
            # Remove TVA note
            transaction.note = "Prélèvement TVA"
            self._createFecRecordFromBankTransaction(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
            self._createFecRecordFromBankTransaction(transaction, "BQ", "44551", 0, -transaction.amount_excluding_vat, num)

        else:
            for account in self.leadger_account_db.accounts:
                if transaction.category in account.thirdparty_names_or_quonto_categories:
                    # Exception : financial revenue and capital increase
                    if account.code in ["764", "1013", "4551"] and transaction.amount_excluding_vat > 0 and transaction.vat == 0:
                        num = self._getNextOpCounter(transaction.when)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", "512", 0, transaction.amount_excluding_vat, num)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", account.code, transaction.amount_excluding_vat, 0, num)

                    # Exception : owner revenue
                    elif account.code in ["6411", "4551", "431"] and transaction.amount_excluding_vat < 0 and transaction.vat == 0:
                        num = self._getNextOpCounter(transaction.when)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", account.code, 0, -transaction.amount_excluding_vat, num)

                    # Exception : Taxes (CET)
                    elif account.code == "63511" and transaction.amount_excluding_vat < 0 and transaction.vat == 0:
                        rec = self._getNextReconciliation()
                        num = self._getNextOpCounter(transaction.when)
                        self._createFecRecordFromBankTransaction(transaction, "OD", "447", -transaction.amount_excluding_vat, 0, num, rec)
                        self._createFecRecordFromBankTransaction(transaction, "OD", account.code, 0, -transaction.amount_excluding_vat, num)
                        num = self._getNextOpCounter(transaction.when)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", "447", 0, -transaction.amount_excluding_vat, num, rec)

                    # Expenses
                    elif account.code[0:1] == "6" and transaction.amount_excluding_vat < 0:
                        amount = -transaction.amount_excluding_vat - transaction.vat
                        rec = self._getNextReconciliation()
                        num = self._getNextOpCounter(transaction.when)
                        self._createFecRecordFromBankTransaction(transaction, "AC", "401", amount, 0, num, rec)
                        self._createFecRecordFromBankTransaction(transaction, "AC", account.code, 0, -transaction.amount_excluding_vat, num)
                        if transaction.vat != 0:
                            self._createFecRecordFromBankTransaction(transaction, "AC", "445661", 0, -transaction.vat, num)
                        num = self._getNextOpCounter(transaction.when)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", "512", amount, 0, num)
                        self._createFecRecordFromBankTransaction(transaction, "BQ", "401", 0, amount, num, rec)

        if len(transaction.fec_records) == 0:
            raise RuntimeError(f"Transaction not supported yet, please create new rules or update configuration : {transaction}")

    def doAccountingForMiscTransactionBefore(self, when: Optional[datetime]) -> None:
        misc_transactions = self.misc_transaction_db.getUntil(when)
        for misc_transaction in misc_transactions:
            num = None
            for entry in misc_transaction.Entries:
                self.doAccountingForInvoicesBefore(misc_transaction.EcritureDate)
                if num is None:
                    num = self._getNextOpCounter(None)
                fec_record = FecRecord(
                    when=misc_transaction.EcritureDate,
                    label=misc_transaction.EcritureLib,
                    journal=entry.Journal,
                    account=entry.Account,
                    evidence=self.evidence_db.get_or_add("GoogleDrive", misc_transaction.PieceRef, misc_transaction.PieceDate),
                    credit_cent=entry.Credit,
                    debit_cent=entry.Debit,
                    ecriture_num=num,
                    ecriture_rec=None
                )
                self.fec_records.append(fec_record)

    def doAccountingForInvoicesBefore(self, when: Optional[datetime]) -> None:
        lastRecordWhen = conv_date_from_utc_to_local(self.start_date)
        if len(self.fec_records):
            lastRecordWhen = conv_date_from_utc_to_local(datetime.strptime(self.fec_records[-1].EcritureDate, "%Y%m%d"))

        for invoice in self.invoices:

            # Customer invoices
            if not invoice.fec_record and (not when or invoice.when <= when) and invoice.type in [CLIENT_CREDIT, CLIENT_INVOICE]:
                num = self._getNextOpCounter(None)
                fecRecord = FecRecord(
                    when=max(invoice.when, lastRecordWhen),
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('VE'),
                    account=self.leadger_account_db.get_or_create('411', invoice.thirdparty_name),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=abs(invoice.total_amount_cent) if invoice.type == CLIENT_CREDIT else 0,
                    debit_cent=invoice.total_amount_cent if invoice.type == CLIENT_INVOICE else 0,
                    ecriture_num=num,
                    ecriture_rec=None
                )
                invoice.fec_record = fecRecord
                self.fec_records.append(fecRecord)

                self.fec_records.append(FecRecord(
                    when=max(invoice.when, lastRecordWhen),
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('VE'),
                    account=self.leadger_account_db.get_by_code_or_fail('706'),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=invoice.amount_excluding_vat_cent if invoice.type == CLIENT_INVOICE else 0,
                    debit_cent=abs(invoice.amount_excluding_vat_cent) if invoice.type == CLIENT_CREDIT else 0,
                    ecriture_num=num,
                    ecriture_rec=None
                ))

                self.fec_records.append(FecRecord(
                    when=max(invoice.when, lastRecordWhen),
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('VE'),
                    account=self.leadger_account_db.get_by_code_or_fail('4458'),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=invoice.amount_vat_cent if invoice.type == CLIENT_INVOICE else 0,
                    debit_cent=abs(invoice.amount_vat_cent) if invoice.type == CLIENT_CREDIT else 0,
                    ecriture_num=num,
                    ecriture_rec=None
                ))

            # Supplier invoices
            if not invoice.fec_record and (not when or invoice.when <= when) and invoice.type in [SUPPLIER_INVOICE]:

                expense_account = 'THIRD_PARTY_ACCOUNT_NOT_FOUND'
                vat_rate = 0.0
                if invoice.thirdparty_name == "INTUITU ASSOCIES":
                    expense_account = '6226'
                    vat_rate = 0.2

                num = self._getNextOpCounter(None)
                fecRecord = FecRecord(
                    when=max(invoice.when, lastRecordWhen),
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('AC'),
                    account=self.leadger_account_db.get_or_create('401', invoice.thirdparty_name),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=round(invoice.total_amount_cent * (1 + vat_rate)),
                    debit_cent=0,
                    ecriture_num=num,
                    ecriture_rec=None
                )
                invoice.fec_record = fecRecord
                self.fec_records.append(fecRecord)

                self.fec_records.append(FecRecord(
                    when=max(invoice.when, lastRecordWhen),
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('AC'),
                    account=self.leadger_account_db.get_by_code_or_fail(expense_account),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=0,
                    debit_cent=abs(invoice.amount_excluding_vat_cent),
                    ecriture_num=num,
                    ecriture_rec=None
                ))

                self.fec_records.append(FecRecord(
                    when=max(invoice.when, lastRecordWhen),
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('AC'),
                    account=self.leadger_account_db.get_by_code_or_fail('445661'),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=0,
                    debit_cent=round(abs(invoice.amount_excluding_vat_cent) * vat_rate),
                    ecriture_num=num,
                    ecriture_rec=None
                ))

    def computeBalances(self) -> Dict[Any, int]:

        balances: Dict[str, int] = {}

        for fec_record in self.fec_records:
            change = fec_record.getCreditAsCent() - fec_record.getDebitAsCent()

            groups = [
                fec_record.CompteNum[0:1],
                f"{fec_record.CompteNum} ({fec_record.CompteLib})"]

            for group in groups:
                if group in balances:
                    balances[group] += change
                else:
                    balances[group] = change

        return balances

    def displayCumulativeMonthlyBalance(self) -> None:
        headers = ["Account", "Label"]
        for fec in self.fec_records:
            if fec.EcritureDate[0:6] not in headers:
                headers.append(fec.EcritureDate[0:6])

        # Init table
        accounts = list(set([(fec.CompteNum, fec.CompteLib) for fec in self.fec_records]))
        accounts.sort()
        data = []
        for ac, la in accounts:
            data.append([ac, la] + ([0.0] * (len(headers) - 2)))

        # Do account value computation
        for fec in self.fec_records:
            for i, h in enumerate(headers):
                for a in data:
                    if fec.CompteNum == str(a[0]) and h == fec.EcritureDate[0:6]:
                        for month in range(i, self.getNbMonths()+3):
                            a[month] = float(a[month]) + float(fec.getCreditAsCent() - fec.getDebitAsCent())/100

        # Add subtotals lines
        last_group = None
        group_sum: List[float | str] = ["1", ""] + ([0.0] * (len(data[0])-2))
        group_sum_1_5: List[float | str] = ["1+2+3+4+5", "==="] + ([0.0] * (len(data[0])-2))
        group_sum_6_7: List[float | str] = ["6+7", "==="] + ([0.0] * (len(data[0])-2))
        data_with_group: List[Any] = []
        for line in data:
            current_group = str(line[0])[0]
            if current_group != last_group and last_group:
                # Next group
                data_with_group.append(["===", "==="] + (["==="] * (len(data[0])-2)))
                data_with_group.append(group_sum)
                data_with_group.append(["", ""] + ([""] * (len(data[0])-2)))
                group_sum = [current_group, ""] + ([0.0] * (len(data[0])-2))

            for i, value in enumerate(line):
                if type(value) is float:
                    if type(group_sum[i]) is float:
                        group_sum[i] = float(group_sum[i]) + value
                    if current_group in ["1", "2", "3", "4", "5"] and type(group_sum_1_5[i]) is float:
                        group_sum_1_5[i] = float(group_sum_1_5[i]) + value
                    if current_group in ["6", "7"] and type(group_sum_6_7[i]) is float:
                        group_sum_6_7[i] = float(group_sum_6_7[i]) + value

            last_group = current_group
            data_with_group.append(line)

        # last subtotal
        data_with_group.append(["===", "==="] + (["==="] * (len(data[0])-2)))
        data_with_group.append(group_sum)
        data_with_group.append(["", ""] + ([""] * (len(data[0])-2)))

        # main subtotal
        data_with_group.append(group_sum_1_5)
        data_with_group.append(group_sum_6_7)

        # Round all values (prettier)
        data_with_group_rounded = [[(round(value) if type(value) is float else value) for value in line] for line in data_with_group]

        def color_row(row: List[Any], i: int) -> List[Any]:
            if len(row[0]) == 1 or "===" in row[0] or "+" in row[0]:
                return [Fore.MAGENTA + str(cell) + Style.RESET_ALL for cell in row]
            elif i % 2 == 0:
                return [Fore.WHITE + str(cell) + Style.RESET_ALL for cell in row]
            else:
                return [Fore.BLUE + str(cell) + Style.RESET_ALL for cell in row]

        data_with_group_rounded_colored = [color_row(row, i) for i, row in enumerate(data_with_group_rounded)]
        print(f"\n{'=' * 20}\nBalance\n{'=' * 20}\n")
        print(tabulate(data_with_group_rounded_colored, headers=headers, colalign=(["left", "left"] + ["right"] * (len(data[0])-2))))

    def validateFec(self) -> None:
        """Controle FEC information with some basic validation rules"""

        # Group FEC line per accouting operation
        fec_dict: Dict[str, List[FecRecord]] = {}
        when_mem = None
        valid_when_mem = None
        carry_forward = 0
        for fec in self.fec_records:
            when = conv_date_from_utc_to_local(fec.EcritureDate)
            if when_mem and when < when_mem:
                logging.error(f"Record {fec}, accouting operation date breaks chronologic order")
            when_mem = when

            valid_when = conv_date_from_utc_to_local(fec.ValidDate)
            if valid_when_mem and valid_when < valid_when_mem:
                logging.error(f"Record {fec}, the validation date {fec} breaks chronologic order")
            if valid_when < when_mem:
                logging.error(f"Record {fec}, the validation date is before tje accouting operation date")
            valid_when_mem = valid_when

            fiscal_period_start = conv_date_from_utc_to_local(self.start_date)
            fiscal_period_end = conv_date_from_utc_to_local(self.end_date)
            if when < fiscal_period_start or when > fiscal_period_end:
                logging.error(f"Record {fec}, date outside fiscal period")

            if valid_when < fiscal_period_start or valid_when > fiscal_period_end:
                logging.error(f"Record {fec}, valid date outside fiscal period")

            reconciliation_when = conv_date_from_utc_to_local(fec.DateLet) if fec.DateLet else None
            if reconciliation_when and (reconciliation_when < fiscal_period_start or reconciliation_when > fiscal_period_end):
                logging.error(f"Record {fec}, reconciliation date outside fiscal period")

            if fec.getCreditAsCent() != 0 and fec.getDebitAsCent() != 0:
                logging.error(f"Record {fec} has credit and also debit amount defined")

            if fec.getCreditAsCent() == 0 and fec.getDebitAsCent() == 0:
                logging.error(f"Record {fec} has zero credit and debit")

            if fec.JournalCode == "AN":
                carry_forward += fec.getCreditAsCent() - fec.getDebitAsCent()

            if fec.EcritureNum in fec_dict:
                fec_dict[fec.EcritureNum].append(fec)
            else:
                fec_dict[fec.EcritureNum] = [fec]

        # Reconciliation balance
        amount_per_reconciliation: Dict[str, int] = {}
        for fec in self.fec_records:
            if fec.EcritureLet and fec.EcritureLet in amount_per_reconciliation:
                amount_per_reconciliation[fec.EcritureLet] += fec.getCreditAsCent() - fec.getDebitAsCent()

            if fec.EcritureLet and fec.EcritureLet not in amount_per_reconciliation:
                amount_per_reconciliation[fec.EcritureLet] = fec.getCreditAsCent() - fec.getDebitAsCent()

        for reconcialiation, amount in amount_per_reconciliation.items():
            if amount != 0:
                logging.error(f"Reconcialiation {reconcialiation} is not balanced : {amount}")

        # Check carry forward balance
        if carry_forward != 0:
            logging.error(f"Unbalanced carry forward balance : {carry_forward}")

        # Check balance per operation
        for num, fec_list in fec_dict.items():
            if sum([fec.getCreditAsCent() for fec in fec_list]) != sum([fec.getDebitAsCent() for fec in fec_list]):
                logging.error(f"Operation {num} is not balanced")

    def addSocialTaxesProvision(self) -> None:
        end_date = datetime.strptime(str(self.end_date), "%Y-%m-%d")

        mandatory_total_cent = 0
        madelin_total_cent = 0
        for fec_record in self.fec_records:
            # Already paid
            if fec_record.CompteNum == "646":
                mandatory_total_cent -= fec_record.getDebitAsCent() - fec_record.getCreditAsCent()

            # Should have been paid
            if fec_record.CompteNum[0:3] == "641":

                # ACRE
                tax_rate = 0.455
                if datetime.strptime(fec_record.EcritureDate, "%Y%m%d") < datetime.strptime("20240731", "%Y%m%d"):
                    tax_rate = 0.167

                if fec_record.CompteNum != "64114":
                    mandatory_total_cent += round(float(fec_record.getDebitAsCent() - fec_record.getCreditAsCent()) * tax_rate)
                else:
                    madelin_total_cent += round(float(fec_record.getDebitAsCent() - fec_record.getCreditAsCent()) * tax_rate)

        if madelin_total_cent > 167400:
            mandatory_total_cent += madelin_total_cent - 167400
            madelin_total_cent = 167400

        num = self._getNextOpCounter(None)
        self.fec_records.append(FecRecord(
            when=end_date,
            label="Provision URSSAF TNS",
            journal=self.journal_db.get_by_code('OD'),
            account=self.leadger_account_db.get_by_code_or_fail('157'),
            evidence=None,
            credit_cent=mandatory_total_cent + madelin_total_cent,
            debit_cent=0,
            ecriture_num=num,
            ecriture_rec=None
        ))

        self.fec_records.append(FecRecord(
            when=end_date,
            label="Provision cotisation sociales exploitant",
            journal=self.journal_db.get_by_code('OD'),
            account=self.leadger_account_db.get_by_code_or_fail('6815'),
            evidence=None,
            credit_cent=0,
            debit_cent=mandatory_total_cent,
            ecriture_num=num,
            ecriture_rec=None
        ))

        self.fec_records.append(FecRecord(
            when=end_date,
            label="Provision URSSAF TNS",
            journal=self.journal_db.get_by_code('OD'),
            account=self.leadger_account_db.get_by_code_or_fail('646100'),
            evidence=None,
            credit_cent=0,
            debit_cent=madelin_total_cent,
            ecriture_num=num,
            ecriture_rec=None
        ))

    def getNbMonths(self) -> int:
        end_date = datetime.strptime(str(self.end_date), "%Y-%m-%d")
        start_date = datetime.strptime(str(self.start_date), "%Y-%m-%d")
        return (end_date.year - start_date.year) * 12 + end_date.month - start_date.month

    def addCompanyTaxes(self) -> None:
        balances = self.computeBalances()
        rcai_cent = (balances["7"] if "7" in balances else 0) + (balances["6"] if "6" in balances else 0)

        if rcai_cent <= 0:
            return

        end_date = datetime.strptime(str(self.end_date), "%Y-%m-%d")
        nb_months = self.getNbMonths()

        reduced_taxes_threshold = round(4250000.0 * nb_months / 12)
        fiscal_due_cent = int(min(rcai_cent, reduced_taxes_threshold) * 0.15 + max(0, rcai_cent - reduced_taxes_threshold) * 0.25)

        last_num = self._getNextOpCounter(None)

        self.fec_records.append(FecRecord(
            when=end_date,
            label="Impôts sur les sociétés",
            journal=self.journal_db.get_by_code("OD"),
            account=self.leadger_account_db.get_by_code_or_fail("6951"),
            credit_cent=0,
            debit_cent=fiscal_due_cent,
            ecriture_num=last_num))

        self.fec_records.append(FecRecord(
              when=end_date,
              label="Impôts sur les sociétés",
              journal=self.journal_db.get_by_code("OD"),
              account=self.leadger_account_db.get_by_code_or_fail("444"),
              credit_cent=fiscal_due_cent,
              debit_cent=0,
              ecriture_num=last_num))

    def doInvoiceAndCreditReconciliation(self) -> None:
        for invoice in self.invoices:
            if invoice.type == CLIENT_CREDIT:
                for invoice_search in self.invoices:
                    if invoice.source_id in invoice_search.associated_credit:
                        rec = self._getNextReconciliation()
                        end_date = datetime.strptime(str(self.end_date), "%Y-%m-%d")
                        if not invoice.fec_record or not invoice_search.fec_record:
                            raise Exception("Technical error 0001")
                        invoice.fec_record.EcritureLet = rec
                        invoice.fec_record.DateLet = end_date.strftime("%Y%m%d")
                        invoice_search.fec_record.EcritureLet = rec
                        invoice_search.fec_record.DateLet = end_date.strftime("%Y%m%d")

    def closeAccouting(self) -> None:

        # Add remaining miscellaneous transaction
        self.doAccountingForMiscTransactionBefore(None)

        # Add remaining invoices
        self.doAccountingForInvoicesBefore(None)

        # Invoice credit reconciliation
        self.doInvoiceAndCreditReconciliation()

        # Add provision
        self.addSocialTaxesProvision()

        # Add taxes
        self.addCompanyTaxes()

        # Validate all operations
        self.validateFec()
