import logging
import os
from dotenv import load_dotenv
from typing import Any
from datetime import datetime
from qonto_fec.qonto import get_transactions
from qonto_fec.fec_accounting import FecAccounting
from qonto_fec.utils import save


def run() -> None:
    # Read configuration
    siren = os.environ.get('company-siren')
    accounting_period_start_date = os.environ.get('accounting-period-start-date')
    accounting_period_end_date = os.environ.get('accounting-period-end-date')
    start_date = datetime.strptime(str(accounting_period_start_date), "%Y-%m-%d")
    end_date = datetime.strptime(str(accounting_period_end_date), "%Y-%m-%d")

    # Get bank transactions
    bank_transactions = get_transactions(accounting_period_start_date, accounting_period_end_date)
    save(bank_transactions, f"{siren}BANK{str(accounting_period_end_date).replace('-','')}")

    # Do accounting from transactions
    accounting = FecAccounting()
    accounting_ops = []
    for bank_transaction in bank_transactions:
        accounting.apply_accouting_rules(bank_transaction)
        if "fec_records" in bank_transaction:
            for fec_record in bank_transaction["fec_records"]:
                fec_record_when = datetime.strptime(fec_record["EcritureDate"], '%Y%m%d')
                if fec_record_when >= start_date and fec_record_when <= end_date:
                    accounting_ops.append(fec_record)

    # Compute accounting balances
    balances, balances_sum_by_group = FecAccounting.get_balances(accounting_ops)

    # Add final accouting to simulate accounts are stopped
    rcai = float(balances_sum_by_group['7']) + float(balances_sum_by_group['6'])
    nb_months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
    fiscal_due = int(min(rcai, 42500*nb_months/12) * 0.15 + max(0, rcai-42500*nb_months/12) * 0.25)

    num = accounting._get_next_ecriture()
    final_transaction: Any = {
        "when": end_date,
        "note": "Impôts sur bénéfices",
        "attachments": "",
        "reference": ""
    }
    accounting.create_fec_record(final_transaction, "OD", "6951", 0, fiscal_due*100, num)
    accounting.create_fec_record(final_transaction, "OD", "444", fiscal_due*100, 0, num)
    accounting_ops.extend(final_transaction["fec_records"])
    balances, balances_sum_by_group = FecAccounting.get_balances(accounting_ops)

    # Display a synthesis
    for balance_group, balance_amount in sorted(balances_sum_by_group.items()):
        print(f"=== {balance_group} : {balance_amount} ===")
        for balance_code, balance_amount in sorted(balances.items()):
              if str(balance_code)[0] == balance_group:
                  print(f"{balance_code} : {balance_amount:.2f}")
    print("\n\n")
    print(f"(1+4+5) = {float(balances_sum_by_group['5']) + float(balances_sum_by_group['4']) + float(balances_sum_by_group['1']):.2f}") 
    print(f"(6+7)= {float(balances_sum_by_group['7']) + float(balances_sum_by_group['6']):.2f}")

    # Export accounting FEC
    save(accounting_ops, f"{siren}FEC{str(accounting_period_end_date).replace('-','')}", False)

    # Export doc source reference
    save(accounting.fec_docs.docs, f"{siren}DOCS{str(accounting_period_end_date).replace('-','')}", False)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    load_dotenv()
    run()
