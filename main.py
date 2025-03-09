import logging
import os
from dotenv import load_dotenv
from qonto2fec.services.accounting import AccountingService
from qonto2fec.services.qonto_client import QontoClient


def run() -> None:

    # Read configuration
    siren = os.environ.get("company-siren")
    if not siren:
        raise Exception("company-siren must be defined")

    accounting_period_start_date = os.environ.get("accounting-period-start-date")
    if not accounting_period_start_date:
        raise Exception("accounting-period-start-date must be defined")

    accounting_period_end_date = os.environ.get("accounting-period-end-date")
    if not accounting_period_end_date:
        raise Exception("accounting_period_end_date must be defined")

    # Qonto API client
    qonto = QontoClient()

    # Accounting service
    accounting_service = AccountingService(siren, accounting_period_start_date, accounting_period_end_date)

    # Handles client invoices and credit notes
    invoices = qonto.getClientInvoices(accounting_period_start_date, accounting_period_end_date)
    accounting_service.addInvoices(invoices)
    credit_notes = qonto.getClientCreditNotes(accounting_period_start_date, accounting_period_end_date)
    accounting_service.addInvoices(credit_notes)

    # Handles bank transactions
    bank_transactions = qonto.getTransactions(accounting_period_start_date, accounting_period_end_date)
    logging.info(f"{len(bank_transactions)} bank transactions retrieved from Qonto")
    for bank_transaction in bank_transactions:
        accounting_service.doAccountingForBankTransaction(bank_transaction)

    # Closes accounting period properly
    accounting_service.closeAccouting()

    # Computes and display balances
    accounting_service.displayBalances()
    accounting_service.displayMonthlyBalance()

    # Saves accounting work to disk
    accounting_service.save()


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    load_dotenv()
    run()
