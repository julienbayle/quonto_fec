import csv
import logging
import os
from typing import Any, Dict, List


DELIMITER = "\t"
QUOTECHAR = '"'


def save_dict_to_csv(data: List[Dict[str, Any]], name: str, escape: bool = True) -> None:
    """
    Saves a python dict to a CSV file in the export subfolder
    """
    if not os.path.exists("./export/"):
        os.makedirs("./export/")

    file_path = f"./export/{name.replace('/', '').replace('-','')}.txt"

    count = len(data)
    if count == 0:
        raise ValueError(f"{file_path} can't be successfully saved, no content")

    quoting_mode = csv.QUOTE_MINIMAL if escape else csv.QUOTE_NONE
    with open(file_path, "w", newline="") as csvFile:
        keys = data[0].keys()
        csvwriter = csv.DictWriter(csvFile, keys, delimiter=DELIMITER, quotechar=QUOTECHAR, quoting=quoting_mode, extrasaction="ignore")
        csvwriter.writeheader()
        csvwriter.writerows(data)

    logging.info(f"{file_path} has been successfully saved ({count} line{'s' if count > 1 else ''})")


def read_dict_from_csv(name: str, escape: bool = True) -> List[Dict[str, Any]]:
    """
    Reads python dict values from a CSV file available in the export subfolder
    """
    data = []
    file_path = f"./export/{name.replace('/', '').replace('-','')}.txt"
    if os.path.exists(file_path):
        quoting_mode = csv.QUOTE_MINIMAL if escape else csv.QUOTE_NONE
        with open(file_path, "r", newline="") as csvFile:
            csvreader = csv.DictReader(csvFile, delimiter=DELIMITER, quotechar=QUOTECHAR, quoting=quoting_mode)
            for row in csvreader:
                data.append(row)

        count = len(data)
        logging.info(f"{file_path} has been successfully loaded ({count} line{'s' if count > 1 else ''})")
    else:
        logging.info(f"{file_path} does not exists, starting with an empty database")

    return data
