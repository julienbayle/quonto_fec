from datetime import datetime
from typing import Any, Dict, List, Tuple

from .evidence_db import EvidenceDB
from .ledger_account_db import LedgerAccountDB
from .journal_db import JournalDB
from ..models.financial_transaction import FinancialTransaction
from ..models.fec_record import FecRecord, create as CreateFecRecord
from .file_utils import save_dict_to_csv


class AccountingService:

    fec_records: List[FecRecord] = []
    fec_counter: int = 0
    reconciliation_counter: int = 0

    journal_db: JournalDB
    evidence_db: EvidenceDB
    leadger_account_db: LedgerAccountDB

    def __init__(self, siren: str, start_date: str, end_date: str) -> None:
        self.start_date = start_date
        self.end_date = end_date
        self.fec_filename = f"{siren}FEC{str(end_date)}"

        # Load databases
        self.journal_db = JournalDB()
        self.evidence_db = EvidenceDB(f"{siren}EVIDENCES{str(end_date)}")
        self.leadger_account_db = LedgerAccountDB(f"{siren}ACCOUNTS")

    def save(self) -> None:
        # Save FEC records
        save_dict_to_csv([r._asdict() for r in self.fec_records], self.fec_filename, False)

        # Save evidences database
        self.evidence_db.save()

        # Save ledger accounts database
        self.leadger_account_db.save()

    def _get_next_ecriture(self) -> int:
        self.fec_counter += 1
        return self.fec_counter

    def _get_next_reconciliation(self) -> str:
        i1 = self.reconciliation_counter % 26
        i2 = int(self.reconciliation_counter / 26)
        rec = f"{chr(i2 + ord('A') - 1) if i2 > 0 else ''}{chr(i1 + ord('A'))}"
        self.reconciliation_counter += 1
        if i2 > 25:
            raise Exception("Reconciliation limit reached")
        return rec

    def create_fec_record(self, transaction: FinancialTransaction, journal_code: str, account: str,
                          credit: int, debit: int, num: int, rec: str | None = None) -> None:
        # EcritureLib
        ecritureLib = ""

        if transaction.reference is not None and journal_code != "VE":
            ecritureLib += str(transaction.reference).replace("\n", " ").replace("\t", " ")

        if transaction.note is not None and len(transaction.note) > 0:
            ecritureLib += " - " if len(ecritureLib) > 0 else ""
            ecritureLib += str(transaction.note).replace("\n", " ").replace("\t", " ")

        if len(ecritureLib) == 0:
            raise Exception(f"Empty label for transaction {transaction}")

        fecRecord = CreateFecRecord(
            when=transaction.when,
            label=ecritureLib,
            journal=self.journal_db.get_by_code(journal_code),
            account=self.leadger_account_db.get_or_create(account, transaction.thirdparty_name),
            evidences=[self.evidence_db.get_or_add("Qonto", attachment) for attachment in transaction.attachments],
            credit=credit,
            debit=debit,
            ecriture_num=num,
            ecriture_rec=rec
        )
        transaction.attach_fec_record(fecRecord)
        self.fec_records.append(fecRecord)

    def doAccounting(self, transaction: FinancialTransaction) -> None:
        """Apply accounting rules, attach generated FEC records to the transaction
           and append it in fec_records collection
        """

        # Sales
        if "sales" == transaction.category and transaction.amount_excluding_vat > 0:
            rec = self._get_next_reconciliation()
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "VE", "411", 0, transaction.amount_excluding_vat + transaction.vat, num, rec)
            self.create_fec_record(transaction, "VE", "706", transaction.amount_excluding_vat, 0, num)
            self.create_fec_record(transaction, "VE", "44571", transaction.vat, 0, num)
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", 0, transaction.amount_excluding_vat + transaction.vat, num)
            self.create_fec_record(transaction, "BQ", "411", transaction.amount_excluding_vat + transaction.vat, 0, num, rec)

        # Financial investment (starting)
        elif "treasury_and_interco" == transaction.category and transaction.amount_excluding_vat < 0 and transaction.vat == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
            self.create_fec_record(transaction, "BQ", "580", 0, -transaction.amount_excluding_vat, num)
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ1", "580", -transaction.amount_excluding_vat, 0, num)
            self.create_fec_record(transaction, "BQ1", "512001", 0, -transaction.amount_excluding_vat, num)

        # Financial investment (ending)
        elif "treasury_and_interco" == transaction.category and transaction.amount_excluding_vat > 0 and transaction.vat == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ1", "512001", transaction.amount_excluding_vat, 0, num)
            self.create_fec_record(transaction, "BQ1", "580", 0, transaction.amount_excluding_vat, num)
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "580", transaction.amount_excluding_vat, 0, num)
            self.create_fec_record(transaction, "BQ", "512", 0, transaction.amount_excluding_vat, num)

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

            num = self._get_next_ecriture()
            # Remove TVA note
            transaction.note = ""
            self.create_fec_record(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
            self.create_fec_record(transaction, "BQ", "44571", 0, TVA08, num)
            if TVA20 + TVA22 != 0:
                self.create_fec_record(transaction, "BQ", "445661", TVA20 + TVA22, 0, num)

        else:
            for account in self.leadger_account_db.accounts:
                if transaction.category in account.thirdparty_names_or_quonto_categories:
                    # Exception : financial revenue and capital increase
                    if account.code in ["764", "1013", "4551"] and transaction.amount_excluding_vat > 0 and transaction.vat == 0:
                        num = self._get_next_ecriture()
                        self.create_fec_record(transaction, "BQ", "512", 0, transaction.amount_excluding_vat, num)
                        self.create_fec_record(transaction, "BQ", account.code, transaction.amount_excluding_vat, 0, num)

                    # Exception : owner revenue
                    elif account.code in ["6411", "4551", "4486"] and transaction.amount_excluding_vat < 0 and transaction.vat == 0:
                        num = self._get_next_ecriture()
                        self.create_fec_record(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
                        self.create_fec_record(transaction, "BQ", account.code, 0, -transaction.amount_excluding_vat, num)

                    # Exception : Taxes (CET)
                    elif account.code == "63511" and transaction.amount_excluding_vat < 0 and transaction.vat == 0:
                        rec = self._get_next_reconciliation()
                        num = self._get_next_ecriture()
                        self.create_fec_record(transaction, "OD", "447", -transaction.amount_excluding_vat, 0, num, rec)
                        self.create_fec_record(transaction, "OD", account.code, 0, -transaction.amount_excluding_vat, num)
                        num = self._get_next_ecriture()
                        self.create_fec_record(transaction, "BQ", "512", -transaction.amount_excluding_vat, 0, num)
                        self.create_fec_record(transaction, "BQ", "447", 0, -transaction.amount_excluding_vat, num, rec)

                    # Expenses
                    elif account.code[0:1] == "6" and transaction.amount_excluding_vat < 0:
                        rec = self._get_next_reconciliation()
                        num = self._get_next_ecriture()
                        self.create_fec_record(transaction, "AC", "401", -transaction.amount_excluding_vat - transaction.vat, 0, num, rec)
                        self.create_fec_record(transaction, "AC", account.code, 0, -transaction.amount_excluding_vat, num)
                        if transaction.vat != 0:
                            self.create_fec_record(transaction, "AC", "445661", 0, -transaction.vat, num)
                        num = self._get_next_ecriture()
                        self.create_fec_record(transaction, "BQ", "512", -transaction.amount_excluding_vat - transaction.vat, 0, num)
                        self.create_fec_record(transaction, "BQ", "401", 0, -transaction.amount_excluding_vat - transaction.vat, num, rec)

        if len(transaction.fec_records) == 0:
            raise RuntimeError(f"Transaction not supported yet, please create new rules or update configuration : {transaction}")

        # URSSAF
        elif len([r for r in transaction.fec_records if r.CompteNum[0:3] == "641"]) > 0:

            # Hack for ACRE computation in my personnal situation
            tax_rate = 0.4029
            if transaction.when < datetime.strptime("20240731", "%Y%m%d").replace(tzinfo=transaction.when.tzinfo):
                tax_rate = 0.167

            mandatory = len([r for r in transaction.fec_records if r.CompteNum == "6411"]) > 0
            amount_due = int(abs(transaction.amount_excluding_vat * tax_rate))

            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "OD", "646" if mandatory else "646100", 0, amount_due, num)
            self.create_fec_record(transaction, "OD", "4486", amount_due, 0, num)

    def computeBalances(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:

        balances: Dict[str, Any] = {}
        balances_sum_by_group: Dict[str, Any] = {}

        for fec_record in self.fec_records:
            change = float(fec_record.Credit.replace(",", ".")) - float(fec_record.Debit.replace(",", "."))
            group = str(fec_record.CompteNum[0:1])
            label = f"{fec_record.CompteNum} ({fec_record.CompteLib})"

            if label in balances:
                balances[label] = balances[label] + change
            else:
                balances[label] = change

            if group in balances_sum_by_group:
                balances_sum_by_group[group] += change
            else:
                balances_sum_by_group[group] = change

        return balances, balances_sum_by_group

    def addProfitTax(self) -> None:

        # Initial balances
        _, balances_sum_by_group = self.computeBalances()

        # Add final accouting to simulate accounts are stopped
        rcai = float(balances_sum_by_group["7"] if "7" in balances_sum_by_group else 0) + float(balances_sum_by_group["6"])

        if rcai < 0:
            return

        end_date = datetime.strptime(str(self.end_date), "%Y-%m-%d")
        start_date = datetime.strptime(str(self.start_date), "%Y-%m-%d")
        nb_months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
        fiscal_due = int(min(rcai, 42500 * nb_months / 12) * 0.15 * 100 + max(0, rcai - 42500 * nb_months / 12) * 0.25 * 100)

        tax_account = self.leadger_account_db.get_by_code("6951")
        if tax_account is None:
            raise RuntimeError("Account 6951 is missing in accounting configuration")

        self.fec_records.append(CreateFecRecord(
            when=end_date,
            label="Impôts sur bénéfices",
            journal=self.journal_db.get_by_code("OD"),
            account=tax_account,
            credit=0,
            debit=fiscal_due,
            ecriture_num=self._get_next_ecriture()))

        dgfip_account = self.leadger_account_db.get_by_code("444")
        if dgfip_account is None:
            raise RuntimeError("Account 444 is missing in accounting configuration")

        self.fec_records.append(CreateFecRecord(
              when=end_date,
              label="Impôts sur bénéfices",
              journal=self.journal_db.get_by_code("OD"),
              account=dgfip_account,
              credit=fiscal_due,
              debit=0,
              ecriture_num=self._get_next_ecriture()))

    def displayBalances(self) -> None:
        """Display balances to the console"""
        balances, balances_sum_by_group = self.computeBalances()

        for balance_group, balance_amount in sorted(balances_sum_by_group.items()):
            print(f"=== {balance_group} : {balance_amount} ===")
            for balance_code, balance_amount in sorted(balances.items()):
                if str(balance_code)[0] == balance_group:
                    print(f"{balance_code} : {balance_amount:.2f}")
        print("\n\n")
        print(f"(1+4+5) = {float(balances_sum_by_group['5']) + float(balances_sum_by_group['4']) + float(balances_sum_by_group['1']):.2f}")
        print(f"(6+7)= {float(balances_sum_by_group['7']) + float(balances_sum_by_group['6']):.2f}")
