import logging
import os
from dotenv import load_dotenv
from typing import  Any, Dict
from datetime import datetime
from qonto_fec.qonto import get_transactions
from qonto_fec.fec_accounting import FecAccounting
from qonto_fec.utils import save


def run() -> None:
    # Read configuration
    siren = os.environ.get('company-siren')
    accounting_period_start_date = os.environ.get('accounting-period-start-date')
    accounting_period_end_date = os.environ.get('accounting-period-end-date')
    
    # Get bank transactions
    bank_transactions = get_transactions(accounting_period_start_date, accounting_period_end_date)
    save(bank_transactions, f"{siren}BANK{str(accounting_period_end_date).replace('-','')}")

    # Do accounting from transactions
    accounting = FecAccounting()
    accounting_ops = []
    for bank_transaction in bank_transactions:
        accounting.apply_accouting_rules(bank_transaction)
        if "fec_records" in bank_transaction:
            accounting_ops.extend(bank_transaction["fec_records"])

    # Compute accounting balances
    balances, balances_sum_by_group = FecAccounting.get_balances(accounting_ops)

    # Add final accouting to simulate accounts are stopped
    rcai = float(balances_sum_by_group['7']) + float(balances_sum_by_group['6'])
    final_transaction: Any = {
        "when": datetime.now(),
        "note": "Impôts sur bénéfices",
        "attachments": "",
        "reference": ""
    }
    fiscal_due = int(min(rcai, 42000) * 0.15 + max(0, rcai-42000) * 0.25)
    num = accounting._get_next_ecriture()
    accounting.create_fec_record(final_transaction, "OD", "6951", 0, fiscal_due*100, num)
    accounting.create_fec_record(final_transaction, "OD", "444", fiscal_due*100, 0, num)
    # Year 2 : accounting.create_fec_record(final_transaction, "OD", "1061", 100*100, 0)
    # Year 2 : accounting.create_fec_record(final_transaction, "OD", "110", int(rcai - 100 - fiscal_due)*100, 0)
    accounting_ops.extend(final_transaction["fec_records"])
    balances, balances_sum_by_group = FecAccounting.get_balances(accounting_ops)

    # Display a synthesis
    for balance_group, balance_amount in sorted(balances_sum_by_group.items()):
        print(f"=== {balance_group} : {balance_amount} ===")
        for balance_code, balance_amount in sorted(balances.items()):
              if str(balance_code)[0] == balance_group:
                  print(f"{balance_code} : {balance_amount:.2f}")
    
    print("\n\n")
    print(f"(7+6)= {float(balances_sum_by_group['7']) + float(balances_sum_by_group['6']):.2f}")
    print(f"(5+4+1) = {float(balances_sum_by_group['5']) + float(balances_sum_by_group['4']) + float(balances_sum_by_group['1']):.2f}")
  
    # Export accounting FEC
    save(accounting_ops, f"{siren}FEC{str(accounting_period_end_date).replace('-','')}")

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    load_dotenv()
    run()
