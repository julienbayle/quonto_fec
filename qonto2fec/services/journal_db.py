from typing import Dict
from ..models.journal import Journal


class JournalDB:

    journals: Dict[str, Journal] = {}

    def __init__(self) -> None:
        # Load Journal labels from accounting configuration
        with open("config/accounting.cfg", "r") as file:
            config_text = file.read()

        journal_section = False
        for line in config_text.split("\n"):
            line = line.strip()
            if not line or "**" in line:
                continue
            if line[0:2] == "* ":
                journal_section = "Journal" in line
            elif journal_section:
                parts = line.split("\t")
                self.journals[parts[0]] = Journal(parts[0], "".join(parts[1:]))

    def get_by_code(self, code: str) -> Journal:
        if code in self.journals:
            return self.journals[code]
        else:
            raise ValueError(f"No journal with code {code}")
