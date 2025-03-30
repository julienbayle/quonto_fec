import json
import logging
import os
from datetime import datetime, timedelta
from http.client import HTTPSConnection
from operator import attrgetter
from typing import Dict, List
from ..models.financial_transaction import FinancialTransaction
from ..models.invoice import Invoice, CLIENT_INVOICE, CLIENT_CREDIT, SUPPLIER_INVOICE
from .date_utils import conv_date_from_utc_to_local


class QontoClient:
    """Quonto API client"""

    qonto_iban: str
    headers: Dict[str, str]
    conn: HTTPSConnection

    def __init__(self) -> None:
        qonto_iban = os.environ.get("qonto-api-iban")
        if not qonto_iban:
            raise Exception("qonto-api-iban must be defined")

        qonto_key = os.environ.get("qonto-api-key")
        if not qonto_key:
            raise Exception("qonto-api-key must be defined")

        qonto_slug = os.environ.get("qonto-api-slug")
        if not qonto_slug:
            raise Exception("qonto_slug must be defined")

        self.headers = {"authorization": f"{qonto_slug}:{qonto_key}"}
        self.conn = HTTPSConnection("thirdparty.qonto.com")
        self.qonto_iban = qonto_iban

    def getTransactions(self, start_date: str, end_date: str) -> List[FinancialTransaction]:
        """
        Get all account transactions from Qonto Bank between two dates

        https://api-doc.qonto.com/docs/business-api/2c89e53f7f645-list-transactions
        """
        start_date_t = conv_date_from_utc_to_local(start_date)
        end_date_t = conv_date_from_utc_to_local(end_date)
        end_date_t += timedelta(hours=23, minutes=59)

        settled_at_from = f"settled_at_from={start_date_t.strftime('%Y%m%dT%H%M%S.%fZ')}"
        settled_at_to = ""
        if end_date_t < conv_date_from_utc_to_local(datetime.now()):
            settled_at_to = f"&settled_at_to={end_date_t.strftime('%Y%m%dT%H%M%S.%fZ')}"

        transactions = []
        next_page = 1
        includes = "includes[]=vat_details&includes[]=labels&includes[]=attachments"
        while next_page is not None:
            url = f"/v2/transactions?iban={self.qonto_iban}&{includes}&page={next_page}&{settled_at_from}{settled_at_to}"
            self.conn.request("GET", url, "{}", self.headers)
            response = self.conn.getresponse()
            if response.status != 200:
                print(response.read())
                raise Exception(response.status, response.reason)

            data = response.read()
            page = json.loads(data.decode("utf-8"))
            next_page = page["meta"]["next_page"]
            for transaction in page["transactions"]:
                if transaction["status"] == "declined":
                    continue

                if transaction["status"] != "completed":
                    logging.warning(f"Transaction is not yet completed, this could lead to bad accounting results : {transaction}")

                if transaction["status"] == "completed":
                    transaction["settled_at"] = conv_date_from_utc_to_local(transaction["settled_at"])
                    financial_transaction = FinancialTransaction(transaction)
                    if financial_transaction.when >= start_date_t and financial_transaction.when <= end_date_t:
                        transactions.append(financial_transaction)
                    else:
                        raise Exception(f"Technical error - This transaction is out of date range: {financial_transaction}")

        transactions = sorted(transactions, key=attrgetter("when"))

        return transactions

    def getClientInvoices(self, start_date: str, end_date: str) -> List[Invoice]:
        start_date_t = conv_date_from_utc_to_local(start_date)
        end_date_t = conv_date_from_utc_to_local(end_date)
        end_date_t += timedelta(hours=23, minutes=59)

        created_at_from = f"filter[created_at_from]={start_date_t.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"
        created_at_to = f"filter[created_at_to]={end_date_t.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"

        invoices = []
        next_page = 1
        while next_page is not None:
            url = f"/v2/client_invoices?{created_at_from}&{created_at_to}&page={next_page}"
            self.conn.request("GET", url, "{}", self.headers)
            response = self.conn.getresponse()
            if response.status != 200:
                print(response.read())
                raise Exception(response.status, response.reason)

            data = response.read()
            raw_invoices = json.loads(data.decode("utf-8"))
            next_page = raw_invoices["meta"]["next_page"]

            for raw_invoice in raw_invoices["client_invoices"]:
                invoice = Invoice(
                    type=CLIENT_INVOICE,
                    source_name="Qonto",
                    source_id=raw_invoice["id"],
                    source_attachment_id=raw_invoice["attachment_id"],
                    when=conv_date_from_utc_to_local(raw_invoice["issue_date"]),
                    number=raw_invoice["number"],
                    total_amount_cents=raw_invoice["total_amount_cents"],
                    amount_vat_cent=raw_invoice["vat_amount_cents"],
                    thirdparty_name=raw_invoice["client"]["name"]
                )

                if raw_invoice["credit_notes_ids"]:
                    invoice.associated_credit = raw_invoice["credit_notes_ids"]

                invoices.append(invoice)

        invoices = sorted(invoices, key=attrgetter("when"))

        return invoices

    def getClientCreditNotes(self, start_date: str, end_date: str) -> List[Invoice]:
        start_date_t = conv_date_from_utc_to_local(start_date)
        end_date_t = conv_date_from_utc_to_local(end_date)
        end_date_t += timedelta(hours=23, minutes=59)

        created_at_from = f"filter[created_at_from]={start_date_t.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"
        created_at_to = f"filter[created_at_to]={end_date_t.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"

        invoices = []
        next_page = 1
        while next_page is not None:
            url = f"/v2/credit_notes?{created_at_from}&{created_at_to}&page={next_page}"
            self.conn.request("GET", url, "{}", self.headers)
            response = self.conn.getresponse()
            if response.status != 200:
                print(response.read())
                raise Exception(response.status, response.reason)

            data = response.read()
            raw_invoices = json.loads(data.decode("utf-8"))
            next_page = raw_invoices["meta"]["next_page"]

            for raw_invoice in raw_invoices["credit_notes"]:
                invoices.append(Invoice(
                    type=CLIENT_CREDIT,
                    source_name="Qonto",
                    source_id=raw_invoice["id"],
                    source_attachment_id=raw_invoice["attachment_id"],
                    when=conv_date_from_utc_to_local(raw_invoice["issue_date"]),
                    number=raw_invoice["number"],
                    total_amount_cents=raw_invoice["total_amount_cents"],
                    amount_vat_cent=raw_invoice["vat_amount_cents"],
                    thirdparty_name=raw_invoice["client"]["name"]
                ))

        invoices = sorted(invoices, key=attrgetter("when"))

        return invoices

    def getToPaySupplierInvoices(self, start_date: str, end_date: str) -> List[Invoice]:
        start_date_t = conv_date_from_utc_to_local(start_date)
        end_date_t = conv_date_from_utc_to_local(end_date) + timedelta(hours=23, minutes=59)

        invoices = []
        next_page = 1
        while next_page is not None:
            url = f"/v2/supplier_invoices?page={next_page}"
            self.conn.request("GET", url, "{}", self.headers)
            response = self.conn.getresponse()
            if response.status != 200:
                print(response.read())
                raise Exception(response.status, response.reason)

            data = response.read()
            raw_invoices = json.loads(data.decode("utf-8"))
            next_page = raw_invoices["meta"]["next_page"]

            for raw_invoice in raw_invoices["supplier_invoices"]:
                if raw_invoice["status"] not in ["paid", "discarded"]:
                    issue_date = conv_date_from_utc_to_local(raw_invoice["issue_date"])
                    if start_date_t <= issue_date <= end_date_t:
                        invoices.append(Invoice(
                            type=SUPPLIER_INVOICE,
                            source_name="Qonto",
                            source_id=raw_invoice["id"],
                            source_attachment_id=raw_invoice["attachment_id"],
                            when=conv_date_from_utc_to_local(raw_invoice["issue_date"]),
                            number=raw_invoice["invoice_number"],
                            total_amount_cents=round(float(raw_invoice["total_amount"]["value"])*100),
                            amount_vat_cent=0,
                            thirdparty_name=raw_invoice["supplier_name"]
                        ))

        invoices = sorted(invoices, key=attrgetter("when"))

        return invoices
