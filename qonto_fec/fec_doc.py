from typing import Dict, Any, List


class FecDoc:
    """ This class represents a FEC document (evidence piece) """

    docs : List[Dict[str, Any]] = []
    counter : int = 0

    def add(self, doc_id: str, source: str) -> str:
        if doc_id is None or doc_id == "":
            return ""

        for d in self.docs:
            if doc_id == d["source_doc_id"]:
                return self._format(d['fec_doc_number'])
        
        self.counter += 1
        self.docs.append({"fec_doc_number": self.counter, "source": source, "source_doc_id": doc_id})

        return self._format(self.counter)

    def _format(self, counter: int) -> str:
        return f"{counter:05d}"