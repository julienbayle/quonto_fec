import logging
import os
import urllib.request
from typing import List, Any
from datetime import datetime
from tqdm import tqdm
from ..models.evidence import Evidence
from .file_utils import save_dict_to_csv


class EvidenceDB:
    """This class implements a file based evidence database"""

    evidences: List[Evidence] = []
    db_name: str

    def __init__(self, name: str) -> None:
        self.db_name = name

    def get_or_add(self, source: str, reference: str, when: datetime) -> Evidence:
        if source is None or reference == "":
            raise ValueError(f"Invalid evidence, source={source}, reference={reference}")

        for evidence in self.evidences:
            if source == evidence.source and reference == evidence.source_reference:
                return evidence

        new_evidence = Evidence(
            number=len(self.evidences)+1,
            source=source,
            source_reference=reference,
            source_path=None,
            when=when.strftime("%Y%m%d"))
        self.evidences.append(new_evidence)

        return new_evidence

    def save(self) -> None:
        save_dict_to_csv([d._asdict() for d in self.evidences], self.db_name, False)

    def download_evidences(self, qonto_client: Any) -> None:
        """
        Download and save evidence files to the export directory
        """
        if not os.path.exists("./export/EVIDENCES/"):
            os.makedirs("./export/EVIDENCES/")

        logging.info(f"Exporting evidences")
        for evidence in tqdm(self.evidences, desc="Downloading evidences", unit="file"):
            if evidence.source == "Qonto":
                try:
                    info = qonto_client.getAttachmentInfo(evidence.source_reference)
                    url = info["url"]
                    file_name = f"{evidence.number:05d}-{info['file_name']}"
                    file_path = f"./export/EVIDENCES/{file_name}"

                    if not os.path.exists(file_path):
                        logging.debug(f"Downloading evidence {evidence.number} from {evidence.source_reference}...")
                        urllib.request.urlretrieve(url, file_path)
                    else:
                        logging.debug(f"Evidence {evidence.number} already exists, skipping download.")
                    evidence.source_path = file_path
                except Exception as e:
                    logging.error(f"Failed to download evidence {evidence.number}: {e}")