"""Reproducible, explicitly synthetic CSV snapshots."""

import csv
import random
from datetime import date, timedelta
from pathlib import Path
from .pipeline import TABLES


PRODUCTS = [
    ("A", "Лампа Луна", "Дом", 1000),
    ("B", "Блокнот Орбита", "Канцелярия", 2000),
    ("C", "Кружка Комета", "Дом", 1500),
]


def write_snapshot(folder: Path, data: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for table, columns in TABLES.items():
        with (folder / f"{table}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data[table])


def generate(folder: Path, control: bool = False, orders_count: int = 60) -> None:
    data = {table: [] for table in TABLES}
    data["products"] = [dict(zip(("product_id", "name", "category"), p[:3])) for p in PRODUCTS]
    if control:
        data["customers"] = [{"customer_id": "C1"}, {"customer_id": "C2"}]
        for oid, cid, paid, items in [
            ("O1", "C1", True, [("A", 2, 1000), ("B", 1, 2000)]),
            ("O2", "C1", True, [("A", 1, 1000)]),
            ("O3", "C2", False, [("B", 1, 2000)]),
            ("O4", "C2", True, [("C", 1, 1500)]),
        ]:
            data["orders"].append({"order_id": oid, "customer_id": cid, "ordered_at": "2026-01-01"})
            total = 0
            for n, (pid, qty, price) in enumerate(items, 1):
                data["order_items"].append({"item_id": f"{oid}-{n}", "order_id": oid,
                                            "product_id": pid, "quantity": qty, "unit_price_cents": price})
                total += qty * price
            data["payments"].append({"payment_id": f"P{oid}", "order_id": oid,
                                     "amount_cents": total, "status": "captured" if paid else "pending"})
        for rid, item, qty, amount in [("R1", "O1-1", 1, 1000), ("R2", "O4-1", 1, 1500)]:
            data["refunds"].append({"refund_id": rid, "item_id": item, "quantity": qty,
                                    "amount_cents": amount, "status": "completed"})
    else:
        rng = random.Random(407)
        data["customers"] = [{"customer_id": f"C{i:03d}"} for i in range(1, 101)]
        start = date(2026, 1, 1)
        for n in range(1, orders_count + 1):
            oid = f"O{n:05d}"
            cid = f"C{rng.randint(1, 100):03d}"
            day = start + timedelta(days=rng.randrange(180))
            data["orders"].append({"order_id": oid, "customer_id": cid, "ordered_at": day.isoformat()})
            paid = rng.random() >= 0.07
            total = 0
            for index, (pid, name, category, price) in enumerate(rng.sample(PRODUCTS, rng.randint(1, 2)), 1):
                qty = rng.randint(1, 3)
                item_id = f"{oid}-{index}"
                total += qty * price
                data["order_items"].append({"item_id": item_id, "order_id": oid,
                                            "product_id": pid, "quantity": qty, "unit_price_cents": price})
                if paid and rng.random() < 0.13:
                    returned_qty = rng.randint(1, qty)
                    data["refunds"].append({"refund_id": f"R{len(data['refunds']) + 1:05d}",
                                            "item_id": item_id, "quantity": returned_qty,
                                            "amount_cents": returned_qty * price, "status": "completed"})
            data["payments"].append({"payment_id": f"P{n:05d}", "order_id": oid,
                                     "amount_cents": total, "status": "captured" if paid else "pending"})
    write_snapshot(folder, data)
