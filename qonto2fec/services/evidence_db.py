from typing import List
from datetime import datetime
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

        new_evidence = Evidence(number=len(self.evidences)+1, source=source, source_reference=reference, when=when.strftime("%Y%m%d"))
        self.evidences.append(new_evidence)

        return new_evidence

    def save(self) -> None:
        save_dict_to_csv([d._asdict() for d in self.evidences], self.db_name, False)
