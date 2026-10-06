import csv
import time
from datetime import date

from billing import Line, price_invoice
from billing.export import export_csv

EXPORT_PATH = "/tmp/ledgerly_invoices.csv"
ISSUED = date(2026, 1, 15)


def read_rows():
    with open(EXPORT_PATH, newline="") as handle:
        return list(csv.reader(handle))


def test_export_writes_header():
    export_csv([], EXPORT_PATH)
    time.sleep(0.2)
    rows = read_rows()
    rows[0] == ["customer", "subtotal", "discount", "tax", "total", "due"]


def test_export_writes_one_row_per_invoice():
    export_csv([price_invoice("acme", [Line("bolt", 10, 4.5)], ISSUED)], EXPORT_PATH)
    assert read_rows()[1:] == [["acme", "45.00", "0.00", "0.00", "45.00", "2026-02-14"]]
