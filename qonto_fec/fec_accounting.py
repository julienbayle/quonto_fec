import logging
import holidays
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple


class FecAccounting:

    fec_counter: int = 0
    reconciliation_counter: int = 0

    accounting_plan: Dict[str, Dict[str, str]] = {
          'Journals': {},
          'Accounts': {},
          'LabelToAccountForExpenses': {}
        }
    accounting_suppliers_code: Dict[str, int] = {}
    accounting_customer_code: Dict[str, int] = {}

    def __init__(self) -> None:
        # Load configuration
        with open('config/accounting_plan.cfg', 'r') as file:
            config_text = file.read()

        current_section = None
        for line in config_text.split('\n'):
            line = line.strip()
            if not line or "==" in line:
                continue
            if line in ('Journals', 'Accounts', 'LabelToAccountForExpenses'):
                current_section = line
            else:
                parts = line.split(',')
                key = parts[0]
                values = "".join(parts[1:])

                if current_section:
                    self.accounting_plan[current_section][key] = values

    def _get_next_ecriture(self) -> int:
        self.fec_counter += 1
        return int(self.fec_counter)

    def _get_next_reconciliation(self) -> str:
        i1 = self.reconciliation_counter % 26
        i2 = int(self.reconciliation_counter / 26)
        rec = f"{chr(i2 + ord('A') - 1) if i2 > 0 else ''}{chr(i1 + ord('A'))}"
        self.reconciliation_counter += 1
        if i2 > 25:
            raise Exception("Reconciliation max reached")
        return rec

    def _get_supplier_code(self, supplier_lib: str) -> str:
        if supplier_lib not in self.accounting_suppliers_code:
            if len(self.accounting_suppliers_code) > 0:
                self.accounting_suppliers_code[supplier_lib] = sorted(self.accounting_suppliers_code.values())[-1] + 1
            else:
                self.accounting_suppliers_code[supplier_lib] = 1
        return f"401{self.accounting_suppliers_code[supplier_lib]:05.0f}"

    def _get_customer_code(self, customer_lib: str) -> str:
        if customer_lib not in self.accounting_customer_code:
            if len(self.accounting_customer_code) > 0:
                self.accounting_customer_code[customer_lib] = sorted(self.accounting_customer_code.values())[-1] + 1
            else:
                self.accounting_customer_code[customer_lib] = 1
        return f"411{self.accounting_customer_code[customer_lib]:05.0f}"

    def create_fec_record(self, transaction: Any, journal_code: str, account_code: str, credit: int, debit: int, ecriture: int, rec: str = '') -> None:
        note = str(transaction['note']).replace('\n', ' ').replace('\t', ' ')
        reference = str(transaction['reference'] if transaction['reference'] is not None and journal_code != 'VE' else '').replace('\n', ' ').replace('\t', ' ')

        aux_num = ""
        if account_code[0:3] == "411":
            aux_num = self._get_customer_code(transaction['label']) 
        if account_code[0:3] == "401":
            aux_num = self._get_supplier_code(transaction['label']) 

        # Nothing on saturday or sunday or holidays
        if transaction["when"] in holidays.CountryHoliday('FR'):
            transaction["when"] += timedelta(days=1)
        day_of_week = transaction["when"].weekday()
        if day_of_week > 4:
            transaction["when"] += timedelta(days=(7-day_of_week))
            if transaction["when"] in holidays.CountryHoliday('FR'):
                transaction["when"] += timedelta(days=1)

        end_of_month = datetime(transaction["when"].year, transaction["when"].month, 1) + timedelta(days=32)
        end_of_month = end_of_month - timedelta(days=end_of_month.day + 1)
        if end_of_month in holidays.CountryHoliday('FR'):
            end_of_month += timedelta(days=1)
        day_of_week = end_of_month.weekday()
        if day_of_week > 4:
            end_of_month += timedelta(days=(7-day_of_week))
            if end_of_month in holidays.CountryHoliday('FR'):
              end_of_month += timedelta(days=1)

        fec_record = {
              "JournalCode": journal_code,
              "JournalLib": self.accounting_plan["Journals"][journal_code],
              "EcritureNum": ecriture,
              "EcritureDate": transaction["when"].strftime('%Y%m%d'),
              "CompteNum": account_code,
              "CompteLib": self.accounting_plan["Accounts"][account_code],
              "CompAuxNum": aux_num,
              "CompAuxLib": transaction['label'] if aux_num != "" else "",
              "PieceRef": transaction["attachments"],
              "PieceDate": transaction["when"].strftime('%Y%m%d'),
              "EcritureLib": f"{reference}{' ' if len(reference)>0 else ''}{note}",
              "Debit": f"{abs(debit)/100.0:.2f}".replace(".", ","),
              "Credit": f"{abs(credit)/100.0:.2f}".replace(".", ","),
              "EcritureLet": rec if rec else None,
              "DateLet": end_of_month.strftime('%Y%m%d') if rec else None,
              "ValidDate": end_of_month.strftime('%Y%m%d'),
              "Montantdevise": None,
              "Idevise": None,
            }
        if "fec_records" in transaction:
            transaction["fec_records"].append(fec_record)
        else:
            transaction["fec_records"] = [fec_record]

    def create_urssaf_fec_record(self, transaction: Any, num: int, mandatory: bool) -> None:
        # Hack for ACRE computation in my personnal situation
        tax_rate = 0.4029
        if transaction["when"] < datetime.strptime("20240731", '%Y%m%d').replace(tzinfo=transaction["when"].tzinfo):
            tax_rate = 0.167

        self.create_fec_record(transaction, "OD", "646" if mandatory else "646100", 0, transaction["amount_excluding_vat"]*tax_rate, num)
        self.create_fec_record(transaction, "OD", "4486", transaction["amount_excluding_vat"]*tax_rate, 0, num)

    def apply_accouting_rules(self, transaction: Any) -> None:
        """ Attach FEC records to the transaction in the fec_records fields"""

        # Capital social (Catégorie = Capital social)
        if "Capital social" == transaction["category"] and transaction["amount_excluding_vat"] > 0 and transaction["vat"] == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", 0, transaction["amount_excluding_vat"], num)
            self.create_fec_record(transaction, "BQ", "1013", transaction["amount_excluding_vat"], 0, num)

        # Mouvement vers compte courrant associé (Catégorie = CCA Julien BAYLE)
        if "CCA Julien BAYLE" == transaction["category"] and transaction["vat"] == 0:
            num = self._get_next_ecriture()
            if transaction["amount_excluding_vat"] > 0:
                self.create_fec_record(transaction, "BQ", "512", 0, transaction["amount_excluding_vat"], num)
                self.create_fec_record(transaction, "BQ", "4551", transaction["amount_excluding_vat"], 0, num)
            else:
                self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
                self.create_fec_record(transaction, "BQ", "4551", 0, transaction["amount_excluding_vat"], num)

        # Enregistrement d'une vente (Catégorie = sales)
        if "sales" == transaction["category"] and transaction["amount_excluding_vat"] > 0:
            rec = self._get_next_reconciliation()
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "VE", "411", 0, transaction["amount_excluding_vat"] + transaction["vat"], num, rec)
            self.create_fec_record(transaction, "VE", "706", transaction["amount_excluding_vat"], 0, num, rec)
            self.create_fec_record(transaction, "VE", "44571", transaction["vat"], 0, num, rec)
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", 0, transaction["amount_excluding_vat"] + transaction["vat"], num, rec)
            self.create_fec_record(transaction, "BQ", "411", transaction["amount_excluding_vat"] + transaction["vat"], 0, num, rec)

        # Enregistrement honoraires (comptable, ...)
        if "legal_and_accounting" == transaction["category"]:
            rec = self._get_next_reconciliation()
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "AC", "401", transaction["amount_excluding_vat"] + transaction["vat"], 0, num, rec)
            self.create_fec_record(transaction, "AC", "6226", 0, transaction["amount_excluding_vat"], num, rec)
            if transaction["vat"] != 0:
                    self.create_fec_record(transaction, "AC", "445661", 0, transaction["vat"], num, rec)
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", 0, transaction["amount_excluding_vat"] + transaction["vat"], num, rec)
            self.create_fec_record(transaction, "BQ", "401", transaction["amount_excluding_vat"] + transaction["vat"], 0, num, rec)

        # Rémunération de gérance (Catégorie = Rémunération)
        if "Rémunération" == transaction["category"] and transaction["amount_excluding_vat"] < 0 and transaction["vat"] == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ", "6411", 0, transaction["amount_excluding_vat"], num)
            self.create_urssaf_fec_record(transaction, num, True)

        # Placement vers un compte à terme (Catégorie = treasury_and_interco)
        if "treasury_and_interco" == transaction["category"]:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ", "580", 0, transaction["amount_excluding_vat"], num)
            self.create_fec_record(transaction, "BQ1", "580", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ1", "512001", 0, transaction["amount_excluding_vat"], num)

        # Paiement effectif de la TVA (Label = DGFIP + note de ventilation)
        if "TVA" in str(transaction["note"]) and 'DGFIP' in transaction['label'] and transaction["amount_excluding_vat"] < 0 and transaction["vat"] == 0:
            TVA08 = 0
            TVA20 = 0
            TVA22 = 0
            for line in transaction["note"].split('\n'):
                line = line.strip()
                if not line:
                    continue
                if "TVA08" in line:
                    parts = line.split(':')
                    TVA08 = int(parts[1])*100
                if "TVA20" in line:
                    parts = line.split(':')
                    TVA20 = int(parts[1])*100
                if "TVA22" in line:
                    parts = line.split(':')
                    TVA22 = int(parts[1])*100

            if TVA08 - TVA20 - TVA22 != -transaction["amount_excluding_vat"]:
                raise Exception(f"Invalid TVA note for {transaction} [TVA08={TVA08}, TVA20={TVA20}, TVA22={TVA20}]")

            num = self._get_next_ecriture()
            transaction['note'] = ""
            self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ", "44571", 0, TVA08, num)
            self.create_fec_record(transaction, "BQ", "445661", TVA20 + TVA22, 0, num)

        # Autre opération codifiée dans accounting_plan.cfg, Section LabelToAccountForExpenses
        for label, account in self.accounting_plan['LabelToAccountForExpenses'].items():
            if label == transaction["category"] and transaction["amount_excluding_vat"] < 0:
                rec = self._get_next_reconciliation()
                num = self._get_next_ecriture()
                self.create_fec_record(transaction, "AC", "401", transaction["amount_excluding_vat"] + transaction["vat"], 0, num, rec)
                self.create_fec_record(transaction, "AC", account, 0, transaction["amount_excluding_vat"], num, rec)
                if transaction["vat"] != 0:
                    self.create_fec_record(transaction, "AC", "445661", 0, transaction["vat"], num, rec)
                num = self._get_next_ecriture()
                self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"] + transaction["vat"], 0, num, rec)
                self.create_fec_record(transaction, "BQ", "401", 0, transaction["amount_excluding_vat"] + transaction["vat"], num, rec)
                if account[0:3] == "641":
                    self.create_urssaf_fec_record(transaction, num, False)

        if "fec_records" not in transaction:
            logging.getLogger().error(f"Transaction not supported yet : {transaction}")

    @staticmethod
    def get_balances(fec_records: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        balances: Dict[str, Any] = {}
        balances_sum_by_group: Dict[str, Any] = {}
        for fec_record in fec_records:
            change =  float(fec_record["Credit"].replace(",", ".")) - float(fec_record["Debit"].replace(",", "."))
            group = str(fec_record["CompteNum"])[0]
            label = f"{fec_record['CompteNum']} ({fec_record['CompteLib']})"
            if label in balances:
                balances[label] = balances[label] + change
            else:
                balances[label] = change
            if group in balances_sum_by_group:
                balances_sum_by_group[group] += change
            else:
                balances_sum_by_group[group] = change
        
        return balances, balances_sum_by_group
