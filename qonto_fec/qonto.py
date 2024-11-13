import os
from http.client import HTTPSConnection
import json
import pytz
import logging
from datetime import datetime
from operator import itemgetter
from typing import Dict, Set, Any, Optional


def get_transactions(start: Optional[str], end: Optional[str]) -> Any:
    """
    Get all account transactions from Qonto Bank

    https://api-doc.qonto.com/docs/business-api/2c89e53f7f645-list-transactions
    """

    qonto_key = os.environ.get('qonto-api-key')
    qonto_slug = os.environ.get('qonto-api-slug')
    qonto_iban = os.environ.get('qonto-api-iban')

    headers = {'authorization': f"{qonto_slug}:{qonto_key}"}
    conn = HTTPSConnection("thirdparty.qonto.com")

    transactions = []
    next_page = 1
    while next_page is not None:
        url = f"/v2/transactions?iban={qonto_iban}&includes[]=vat_details&includes[]=labels&includes[]=attachments&page={next_page}"
        conn.request("GET", url, "{}", headers)
        response = conn.getresponse()
        if response.status != 200:
            raise Exception(response.status, response.reason)

        data = response.read()
        page = json.loads(data.decode("utf-8"))
        next_page = page['meta']['next_page']
        transactions.extend(page["transactions"])

    return sorted([prepare_and_validate(t) for t in transactions], key=itemgetter('when'))

def _conv_utc(date: str) -> Any:
    """
    Convert the UTC timestamp in fetched records to Europe/Paris TZ (YYYY-MM-DD HH:mm:ss).

    Args:
        date (str): UTC timestamp (YYYY-MM-DDTHH:mm:ss.sssZ)
    Returns:
        local date converted to Europe/Paris TZ (YYYY-MM-DD HH:mm:ss)
    """
    local_tz = pytz.timezone('Europe/Paris')
    utc_tz = pytz.timezone('UTC')
    dt_utc = utc_tz.localize(datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ'))
    dt_local = local_tz.normalize(dt_utc)
    return dt_local

def prepare_and_validate(transaction: Any) -> Dict[str, Any]:
    """
    Validate each transaction is ready to be processed by the accounting process
    If not, raise an Exception. Then improve the data format to ease the next steps

    Returns:
      cleaned transaction data as a dictionnary
    """
    name = f"{transaction['label']} ({transaction['transaction_id']})"

    if transaction["status"] != "completed":
        logging.getLogger().warn(f"{name} : Transaction is not yet completed, this could lead to bad accouting results")

    if transaction["currency"] != "EUR":
        raise Exception(f"{name}: Only EUR currency is supported")

    if transaction["attachment_required"] and len(transaction["attachments"]) == 0 and not transaction["attachment_lost"] and transaction["operation_type"] != 'qonto_fee':
        raise Exception(f"{name}: Required attachment is missing")

    if len(transaction["label_ids"]) > 1:
        raise Exception(f"{name}: Only one label per transaction is allowed)")

    amount = transaction["amount_cents"]
    side = 1 if transaction["side"] == "credit" else -1

    if "vat_details" in transaction is not None and "items" in transaction["vat_details"] and len(transaction["vat_details"]["items"]) > 0:
        amount_excluding_vat = 0.0
        vat = 0.0
        for vat_detail in transaction["vat_details"]["items"]:
            if vat_detail["rate"] not in [0.0, 5.5, 10, 20]:
                raise Exception(f"{name}: VAT rate not supported : {vat_detail['rate']}")
            amount_excluding_vat += side * vat_detail["amount_excluding_vat_cents"]
            vat += side * vat_detail["amount_cents"]
    else:
        vat = 0.0
        amount_excluding_vat = side * amount

    if vat + amount_excluding_vat != amount * side:
        raise Exception(f"{name}: Amount error ! {vat} + {amount_excluding_vat} != {amount * side}")

    return {
        "amount_excluding_vat": int(amount_excluding_vat),
        "vat": int(vat),
        "when": _conv_utc(transaction["settled_at"]),
        "attachments": ",".join(transaction["attachment_ids"]),
        "category": transaction["category"] if len(transaction["label_ids"]) == 0 else transaction["labels"][0]['name'],
        "label": transaction["label"],
        "note": transaction["note"],
        "reference": transaction["reference"],
        "operation_type": transaction["operation_type"]}
