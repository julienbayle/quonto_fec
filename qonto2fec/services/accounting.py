from datetime import datetime
from typing import Any, Dict, List, Optional
from tabulate import tabulate

from .evidence_db import EvidenceDB
from .ledger_account_db import LedgerAccountDB
from .journal_db import JournalDB
from .misc_transaction_db import MiscellaneousTransactionDB
from ..models.financial_transaction import FinancialTransaction
from ..models.invoice import Invoice
from ..models.fec_record import FecRecord
from .file_utils import save_dict_to_csv


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
        i2 = int(self.reconciliation_counter / 26)
        rec = f"{chr(i2 + ord('A') - 1) if i2 > 0 else ''}{chr(i1 + ord('A'))}"
        self.reconciliation_counter += 1
        if i2 > 25:
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
                    fec_record.EcritureLet = fec.EcritureLet
                    fec_record.DateLet = fec.DateLet

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
                Exception(f"Invoice not found in accounting : {fec.PieceRef} {fec.EcritureLib} {fec.EcritureDate}")

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
            "TVA" in str(transaction.note)
            and "DGFIP" in transaction.thirdparty_name
            and transaction.amount_excluding_vat < 0
            and transaction.vat == 0
        ):
            TVA08 = 0
            TVA20 = 0
            TVA22 = 0
            for line in transaction.note.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "TVA08" in line:
                    parts = line.split(":")
                    TVA08 = int(parts[1]) * 100
                if "TVA20" in line:
                    parts = line.split(":")
                    TVA20 = int(parts[1]) * 100
                if "TVA22" in line:
                    parts = line.split(":")
                    TVA22 = int(parts[1]) * 100

            if TVA08 - TVA20 - TVA22 != -transaction.amount_excluding_vat:
                raise Exception(f"Invalid TVA note for {transaction} [TVA08={TVA08}, TVA20={TVA20}, TVA22={TVA22}]")

            num = self._getNextOpCounter(transaction.when)
            # Remove TVA note
            transaction.note = ""
            self._createFecRecordFromBankTransaction(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
            self._createFecRecordFromBankTransaction(transaction, "BQ", "44571", 0, TVA08, num)
            if TVA20 + TVA22 != 0:
                self._createFecRecordFromBankTransaction(transaction, "BQ", "445661", TVA20 + TVA22, 0, num)

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
        for invoice in self.invoices:
            if not invoice.fec_record and (not when or invoice.when <= when):
                num = self._getNextOpCounter(None)
                fecRecord = FecRecord(
                    when=invoice.when,
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('VE'),
                    account=self.leadger_account_db.get_or_create('411', invoice.thirdparty_name),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=0,
                    debit_cent=invoice.total_amount_cent,
                    ecriture_num=num,
                    ecriture_rec=None
                )
                invoice.fec_record = fecRecord
                self.fec_records.append(fecRecord)

                self.fec_records.append(FecRecord(
                    when=invoice.when,
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('VE'),
                    account=self.leadger_account_db.get_by_code_or_fail('706'),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=invoice.amount_excluding_vat_cent,
                    debit_cent=0,
                    ecriture_num=num,
                    ecriture_rec=None
                ))

                self.fec_records.append(FecRecord(
                    when=invoice.when,
                    label=invoice.number,
                    journal=self.journal_db.get_by_code('VE'),
                    account=self.leadger_account_db.get_by_code_or_fail('4458'),
                    evidence=self.evidence_db.get_or_add("Qonto", invoice.source_attachment_id, invoice.when),
                    credit_cent=invoice.amount_vat_cent,
                    debit_cent=0,
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

    def displayBalances(self) -> None:
        """Display balances to the console"""
        balances = self.computeBalances()

        data = []
        amount_1_2_3_4_5 = 0
        amount_6_7 = 0
        for group, amount in sorted(balances.items()):
            amount_str = FecRecord.centToFrenchFecFormat(amount)
            if len(group) == 1:
                data.append(["", ""])
                data.append([amount_str, f"=== {group} ==="])
            else:
                data.append([amount_str, group])

            if group in ["1", "Z", "3", "4", "5"]:
                amount_1_2_3_4_5 += amount

            if group in ["6", "7"]:
                amount_6_7 += amount

        data.append(["", ""])
        data.append([FecRecord.centToFrenchFecFormat(amount_1_2_3_4_5), "=== 1 + 2 + 3 + 4 + 5 ==="])
        data.append([FecRecord.centToFrenchFecFormat(amount_6_7), "=== 6 + 7 ==="])

        print(f"\n{'=' * 20}\nBalance générale\n{'=' * 20}\n")
        print(tabulate(data, headers=["Montant", "Compte"], colalign=["right", "left"]))

    def displayMonthlyBalance(self) -> None:
        headers = ["Account", "Label"]
        for fec in self.fec_records:
            if fec.EcritureDate[0:6] not in headers:
                headers.append(fec.EcritureDate[0:6])

        accounts = list(set([(fec.CompteNum, fec.CompteLib) for fec in self.fec_records]))
        accounts.sort()
        data = []
        for ac, la in accounts:
            data.append([ac, la] + ([0.0] * (len(headers) - 2)))

        for fec in self.fec_records:
            for i, h in enumerate(headers):
                for a in data:
                    if fec.CompteNum == str(a[0]) and h == fec.EcritureDate[0:6]:
                        a[i] = float(a[i]) + float(fec.getCreditAsCent() - fec.getDebitAsCent())/100

        print(f"\n{'=' * 20}\nBalance mensuelle\n{'=' * 20}\n")
        print(tabulate(data, headers=headers))

    def validateFec(self) -> None:
        """Controle FEC information with some basic validation rules"""

        # Group FEC line per accouting operation
        fec_dict: Dict[str, List[FecRecord]] = {}
        for fec in self.fec_records:
            if fec.getCreditAsCent() != 0 and fec.getDebitAsCent() != 0:
                raise Exception(f"Record {fec} has credit and also debit amount defined")

            if fec.getCreditAsCent() == 0 and fec.getDebitAsCent() == 0:
                raise Exception(f"Record {fec} has zero credit and debit")

            if fec.EcritureNum in fec_dict:
                fec_dict[fec.EcritureNum].append(fec)
            else:
                fec_dict[fec.EcritureNum] = [fec]

        # Check balance per operation
        for num, fec_list in fec_dict.items():
            if sum([fec.getCreditAsCent() for fec in fec_list]) != sum([fec.getDebitAsCent() for fec in fec_list]):
                raise Exception(f"Operation {num} is not balanced")

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
            account=self.leadger_account_db.get_by_code_or_fail('431'),
            evidence=None,
            credit_cent=mandatory_total_cent + madelin_total_cent,
            debit_cent=0,
            ecriture_num=num,
            ecriture_rec=None
        ))

        self.fec_records.append(FecRecord(
            when=end_date,
            label="Provision URSSAF TNS",
            journal=self.journal_db.get_by_code('OD'),
            account=self.leadger_account_db.get_by_code_or_fail('646'),
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

    def addCompanyTaxes(self) -> None:
        balances = self.computeBalances()
        rcai_cent = (balances["7"] if "7" in balances else 0) + (balances["6"] if "6" in balances else 0)

        if rcai_cent <= 0:
            return

        end_date = datetime.strptime(str(self.end_date), "%Y-%m-%d")
        start_date = datetime.strptime(str(self.start_date), "%Y-%m-%d")
        nb_months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month

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

    def closeAccouting(self) -> None:

        # Add remaining miscellaneous transaction
        self.doAccountingForMiscTransactionBefore(None)

        # Add remaining invoices
        self.doAccountingForInvoicesBefore(None)

        # Add provision
        self.addSocialTaxesProvision()

        # Add taxes
        self.addCompanyTaxes()

        # Validate all operations
        self.validateFec()
