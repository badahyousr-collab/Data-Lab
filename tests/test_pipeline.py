import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from datalab.export import export
from datalab.generate import generate
from datalab.pipeline import DataError, load, metrics


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.csv = self.root / "csv"
        self.db = self.root / "sales.db"
        generate(self.csv, control=True)

    def test_hand_calculated_revenue_refunds_and_repeat_buyers(self):
        load(self.csv, self.db)
        self.assertEqual(metrics(self.db), {
            "gross_cents": 6500, "refund_cents": 2500, "revenue_cents": 4000,
            "purchase_count": 2, "repeat_customers": 1,
        })
        target = self.root / "data.json"
        self.assertEqual(export(self.db, target), 4)
        rows = json.loads(target.read_text(encoding="utf-8"))["rows"]
        self.assertEqual(sum(r["gross_cents"] - r["refund_cents"] for r in rows), 4000)
        by_product = {}
        for row in rows:
            by_product[row["name"]] = by_product.get(row["name"], 0) + row["gross_units"] - row["refunded_units"]
        self.assertEqual(by_product, {"Лампа Луна": 2, "Блокнот Орбита": 1, "Кружка Комета": 0})

    def test_repeat_load_is_idempotent(self):
        first = load(self.csv, self.db)
        second = load(self.csv, self.db)
        self.assertEqual(first, second)
        with sqlite3.connect(self.db) as connection:
            for table, count in second.items():
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], count)
        self.assertEqual(metrics(self.db)["revenue_cents"], 4000)

    def test_conflicting_duplicate_rejects_snapshot_without_changing_db(self):
        load(self.csv, self.db)
        path = self.csv / "payments.csv"
        with path.open("a", encoding="utf-8") as stream:
            stream.write("PO1,O1,4000,pending\n")
        with self.assertRaisesRegex(DataError, "conflicting duplicate"):
            load(self.csv, self.db)
        self.assertEqual(metrics(self.db)["revenue_cents"], 4000)

    def test_exact_duplicate_is_ignored(self):
        path = self.csv / "payments.csv"
        with path.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        with path.open("a", encoding="utf-8") as stream:
            stream.write("PO1,O1,4000,captured\n")
        self.assertEqual(load(self.csv, self.db)["payments"], len(rows))

    def test_wrong_refund_amount_rejected(self):
        path = self.csv / "refunds.csv"
        content = path.read_text(encoding="utf-8").replace("R1,O1-1,1,1000,completed", "R1,O1-1,1,999,completed")
        path.write_text(content, encoding="utf-8")
        with self.assertRaisesRegex(DataError, "refund differs"):
            load(self.csv, self.db)

    def test_excessive_returns_and_missing_reference_rejected(self):
        path = self.csv / "refunds.csv"
        with path.open("a", encoding="utf-8") as stream:
            stream.write("R3,O1-1,2,2000,completed\n")
        with self.assertRaisesRegex(DataError, "too many refunded"):
            load(self.csv, self.db)
        path = self.csv / "orders.csv"
        path.write_text(path.read_text(encoding="utf-8").replace("O1,C1", "O1,missing"), encoding="utf-8")
        with self.assertRaisesRegex(DataError, "unknown customer"):
            load(self.csv, self.db)


if __name__ == "__main__":
    unittest.main()
