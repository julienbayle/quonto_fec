import json
import logging
import os
import pytz
from datetime import datetime, timedelta
from http.client import HTTPSConnection
from operator import attrgetter
from typing import Dict, List
from ..models.financial_transaction import FinancialTransaction


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

    @staticmethod
    def _conv_date_from_utc_to_local(date: str | datetime) -> datetime:
        """
        Normalize a date to Europe/Paris timezone from a UTC based date
        """
        if type(date) is str:
            try:
                date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                date = datetime.strptime(str(date), "%Y-%m-%d")
        local_tz = pytz.timezone("Europe/Paris")
        utc_tz = pytz.timezone("UTC")
        dt_utc = utc_tz.localize(date)
        dt_local = local_tz.normalize(dt_utc)
        if type(dt_local) is datetime:
            return dt_local
        else:
            raise ValueError("Technical error - Date is not a datime after conversion")

    def get_transactions(self, siren: str, start_date: str, end_date: str) -> List[FinancialTransaction]:
        """
        Get all account transactions from Qonto Bank between two dates

        https://api-doc.qonto.com/docs/business-api/2c89e53f7f645-list-transactions
        """
        start_date_t = self._conv_date_from_utc_to_local(start_date)
        end_date_t = self._conv_date_from_utc_to_local(end_date)
        end_date_t += timedelta(hours=23, minutes=59)

        settled_at_from = f"settled_at_from={start_date_t.strftime('%Y%m%dT%H%M%S.%fZ')}"
        settled_at_to = f"settled_at_to={end_date_t.strftime('%Y%m%dT%H%M%S.%fZ')}"

        transactions = []
        next_page = 1
        includes = "includes[]=vat_details&includes[]=labels&includes[]=attachments"
        while next_page is not None:
            url = f"/v2/transactions?iban={self.qonto_iban}&{includes}&page={next_page}&{settled_at_from}&{settled_at_to}"
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
                    logging.getLogger().warning(f"Transaction is not yet completed, this could lead to bad accounting results : {transaction}")

                if transaction["status"] == "completed":
                    transaction["settled_at"] = self._conv_date_from_utc_to_local(transaction["settled_at"])
                    financial_transaction = FinancialTransaction(transaction)
                    if financial_transaction.when >= start_date_t and financial_transaction.when <= end_date_t:
                        transactions.append(financial_transaction)
                    else:
                        raise Exception(f"Technical error - This transaction is out of date range: {financial_transaction}")

        transactions = sorted(transactions, key=attrgetter("when"))

        return transactions
