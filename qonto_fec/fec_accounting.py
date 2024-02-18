import logging
from datetime import datetime
from typing import Any, Dict, Tuple


class FecAccounting:
    
    fec_counter: int = 0
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
            if not line:
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

    def create_fec_record(self, transaction: Any, journal_code: str, account_code: str, credit: int, debit: int, ecriture: int) -> None:
        note = str(transaction['note']).replace('\n', ' ')

        aux_num = ""
        if account_code[0:3] == "411":
            aux_num = self._get_customer_code(transaction['label']) 
        if account_code[0:3] == "401":
            aux_num = self._get_supplier_code(transaction['label']) 

        fec_record = {
              "JOURNALCODE": journal_code,
              "JOURNALLIB": self.accounting_plan["Journals"][journal_code],
              "ECRITURENUM": ecriture,
              "ECRITUREDATE": transaction["when"].strftime('%Y%m%d'),
              "COMPTENUM": account_code,
              "COMPTELIB": self.accounting_plan["Accounts"][account_code],
              "COMPAUXNUM": aux_num,
              "COMPAUXLIB": transaction['label'] if aux_num != "" else "",
              "PIECEREF": transaction["attachments"],
              "PIECEDATE": None,
              "ECRITURELIB": f"{transaction['reference'] if transaction['reference'] is not None else ''} {note}",
              "DEBIT": f"{abs(debit)/100.0:.2f}",
              "CREDIT": f"{abs(credit)/100.0:.2f}",
              "ECRITURELET": None,
              "DATELET": None,
              "VALIDDATE": datetime.now().strftime('%Y%m%d'),
              "MONTANTDEVISE": "",
              "IDEVISE": "",
            }
        if "fec_records" in transaction:
            transaction["fec_records"].append(fec_record)
        else:
            transaction["fec_records"] = [fec_record]

    def apply_accouting_rules(self, transaction: Any) -> None:
        """ Attach FEC records to the transaction in the fec_records fields"""

        if "Capital social" == transaction["category"] and transaction["amount_excluding_vat"] > 0 and  transaction["vat"] == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", 0, transaction["amount_excluding_vat"], num)
            self.create_fec_record(transaction, "BQ", "1013", transaction["amount_excluding_vat"], 0, num)

        if "CCA Julien BAYLE" == transaction["category"] and  transaction["vat"] == 0:
            num = self._get_next_ecriture()
            if transaction["amount_excluding_vat"] > 0:
                self.create_fec_record(transaction, "BQ", "512", 0, transaction["amount_excluding_vat"], num)
                self.create_fec_record(transaction, "BQ", "4551", transaction["amount_excluding_vat"], 0, num)
            else:
                self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
                self.create_fec_record(transaction, "BQ", "4551", 0, transaction["amount_excluding_vat"], num)

        if "sales" == transaction["category"] and transaction["amount_excluding_vat"] > 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "VE", "411", 0, transaction["amount_excluding_vat"] + transaction["vat"], num)
            self.create_fec_record(transaction, "VE", "706", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "VE", "44571", transaction["vat"], 0, num)
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", 0, transaction["amount_excluding_vat"] + transaction["vat"], num)
            self.create_fec_record(transaction, "BQ", "411", transaction["amount_excluding_vat"] + transaction["vat"], 0, num)

        if "Rémunération" == transaction["category"] and transaction["amount_excluding_vat"] < 0 and transaction["vat"] == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ", "6411", 0, transaction["amount_excluding_vat"], num)
            self.create_fec_record(transaction, "OD", "646", 0, transaction["amount_excluding_vat"]*0.45, num)
            self.create_fec_record(transaction, "OD", "4486", transaction["amount_excluding_vat"]*0.45, 0, num)

        if "Mutuelle" == transaction["category"] and transaction["amount_excluding_vat"] < 0 and transaction["vat"] == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ", "64114", 0, transaction["amount_excluding_vat"], num)

        if "Charges" == transaction["category"] and transaction["amount_excluding_vat"] < 0 and transaction["vat"] == 0:
            num = self._get_next_ecriture()
            self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ", "4486", 0, transaction["amount_excluding_vat"], num)

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
            self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"], 0, num)
            self.create_fec_record(transaction, "BQ", "44571", 0, TVA08, num)
            self.create_fec_record(transaction, "BQ", "445661", TVA20 + TVA22, 0, num)
            transaction['note'] = ""

        for label, account in self.accounting_plan['LabelToAccountForExpenses'].items():
            if label == transaction["category"] and transaction["amount_excluding_vat"] < 0:
                num = self._get_next_ecriture()
                self.create_fec_record(transaction, "AC", "401", transaction["amount_excluding_vat"] + transaction["vat"], 0, num)
                self.create_fec_record(transaction, "AC", account, 0, transaction["amount_excluding_vat"], num)
                if transaction["vat"] != 0:
                    self.create_fec_record(transaction, "AC", "445661", 0, transaction["vat"], num)
                num = self._get_next_ecriture()
                self.create_fec_record(transaction, "BQ", "512", transaction["amount_excluding_vat"] + transaction["vat"], 0, num)
                self.create_fec_record(transaction, "BQ", "401", 0, transaction["amount_excluding_vat"] + transaction["vat"], num)
                
       
        if "fec_records" not in transaction:
            logging.getLogger().error(f"Transaction not supported yet : {transaction}")


    @staticmethod
    def get_balances(fec_records: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        balances: Dict[str, Any] = {}
        balances_sum_by_group: Dict[str, Any] = {}
        for fec_record in fec_records:
            change =  float(fec_record["CREDIT"]) - float(fec_record["DEBIT"])
            group = str(fec_record["COMPTENUM"])[0]
            label = f"{fec_record['COMPTENUM']} ({fec_record['COMPTELIB']})"
            if label in balances:
                balances[label] = balances[label] + change
            else:
                balances[label] = change
            if group in balances_sum_by_group:
                balances_sum_by_group[group] += change
            else:
                balances_sum_by_group[group] = change
        
        return balances, balances_sum_by_group
