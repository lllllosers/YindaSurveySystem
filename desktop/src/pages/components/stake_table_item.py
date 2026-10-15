from PySide6.QtWidgets import QTableWidgetItem
from shared.protocol.stake import parse_stake


def stake_sort_key(record):
    values = []
    for key, fallback in (("start_stake", "single_stake"), ("end_stake", "single_stake")):
        value = record.get(key + "_value")
        if value is None:
            value = record.get(fallback + "_value")
        if value is None:
            text = record.get(key + "_text") or record.get(fallback + "_text") or ""
            try:
                _, value = parse_stake(text)
            except ValueError:
                value = None
        values.append(float("inf") if value is None else float(value))
    return tuple(values)


class StakeTableItem(QTableWidgetItem):
    def __init__(self, text, key):
        super().__init__(text)
        self.sort_key = key

    def __lt__(self, other):
        return self.sort_key < other.sort_key
