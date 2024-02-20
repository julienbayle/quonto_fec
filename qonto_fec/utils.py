import logging
import csv
import os
from typing import  Any


def save(dict: Any, name: str, escape: bool = True) -> None:
    """
    Save a python dict as a CSV file in the data subfolder
    """
    if not os.path.exists('./data/'):
        os.makedirs('./data/')
    
    file_path = f"./data/{name.replace('/', '')}.txt"
    quoting_mode = csv.QUOTE_MINIMAL if escape else csv.QUOTE_NONE
    with open(file_path, 'w', newline='') as csvFile:
        keys = dict[0].keys()
        csvwriter = csv.DictWriter(csvFile, keys, delimiter='\t', quotechar='"', quoting=quoting_mode, extrasaction="ignore")
        csvwriter.writeheader()
        csvwriter.writerows(dict)

    count = len(dict)
    logging.getLogger().info(f"{file_path} has been successfully generated ({count} line{'s' if count > 1 else ''})")