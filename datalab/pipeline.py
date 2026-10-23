"""Validate a complete CSV snapshot, then atomically replace the local database."""

import csv
import re
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path


TABLES = {
    "customers": ("customer_id",),
    "products": ("product_id", "name", "category"),
    "orders": ("order_id", "customer_id", "ordered_at"),
    "order_items": ("item_id", "order_id", "product_id", "quantity", "unit_price_cents"),
    "payments": ("payment_id", "order_id", "amount_cents", "status"),
    "refunds": ("refund_id", "item_id", "quantity", "amount_cents", "status"),
}
KEYS = ("customer_id", "product_id", "order_id", "item_id", "payment_id", "refund_id")
INTEGER_FIELDS = {"quantity", "unit_price_cents", "amount_cents"}


class DataError(ValueError):
    """Invalid snapshot; nothing should be written to the database."""


def read_snapshot(folder: Path) -> dict:
    data = {}
    for (table, columns), key in zip(TABLES.items(), KEYS):
        path = folder / f"{table}.csv"
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(columns):
                raise DataError(f"{path}: expected columns {columns}, got {reader.fieldnames}")
            rows = {}
            for line, raw in enumerate(reader, 2):
                if None in raw or any(value is None for value in raw.values()):
                    raise DataError(f"{path}:{line}: wrong column count")
                row = {name: value.strip() for name, value in raw.items()}
                if any(not value for value in row.values()):
                    raise DataError(f"{path}:{line}: empty field")
                for name in INTEGER_FIELDS & row.keys():
                    if not re.fullmatch(r"[0-9]+", row[name]) or int(row[name]) <= 0:
                        raise DataError(f"{path}:{line}: {name} must be a positive integer")
                    row[name] = int(row[name])
                previous = rows.get(row[key])
                if previous is not None and previous != row:
                    raise DataError(f"{path}:{line}: conflicting duplicate {row[key]}")
                rows[row[key]] = row
            data[table] = rows
    validate(data)
    return data


def validate(data: dict) -> None:
    def require(condition, message):
        if not condition:
            raise DataError(message)

    for row in data["orders"].values():
        require(row["customer_id"] in data["customers"], f"unknown customer: {row['order_id']}")
        try:
            require(date.fromisoformat(row["ordered_at"]).isoformat() == row["ordered_at"],
                    f"invalid date: {row['order_id']}")
        except ValueError as exc:
            raise DataError(f"invalid date: {row['order_id']}") from exc
    totals = defaultdict(int)
    counts = defaultdict(int)
    for row in data["order_items"].values():
        require(row["order_id"] in data["orders"], f"unknown order: {row['item_id']}")
        require(row["product_id"] in data["products"], f"unknown product: {row['item_id']}")
        totals[row["order_id"]] += row["quantity"] * row["unit_price_cents"]
    require(set(totals) == set(data["orders"]), "each order needs items")
    for row in data["payments"].values():
        order = row["order_id"]
        require(order in data["orders"], f"unknown order: {row['payment_id']}")
        require(row["status"] in {"captured", "pending"}, f"invalid payment status: {row['payment_id']}")
        require(row["amount_cents"] == totals[order], f"payment differs from items: {order}")
        counts[order] += 1
    require(set(counts) == set(data["orders"]) and all(n == 1 for n in counts.values()),
            "each order needs exactly one payment")
    paid = {row["order_id"] for row in data["payments"].values() if row["status"] == "captured"}
    returned = defaultdict(int)
    for row in data["refunds"].values():
        item = data["order_items"].get(row["item_id"])
        require(item is not None, f"unknown item: {row['refund_id']}")
        require(row["status"] in {"completed", "pending"}, f"invalid refund status: {row['refund_id']}")
        require(item["order_id"] in paid, f"refund for unpaid order: {row['refund_id']}")
        require(row["amount_cents"] == row["quantity"] * item["unit_price_cents"],
                f"refund differs from item price: {row['refund_id']}")
        if row["status"] == "completed":
            returned[row["item_id"]] += row["quantity"]
            require(returned[row["item_id"]] <= item["quantity"],
                    f"too many refunded units: {row['item_id']}")


def load(folder: Path, database: Path) -> dict:
    data = read_snapshot(folder)
    database.parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent.parent / "sql/schema.sql").read_text(encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema)
        # A snapshot replacement is atomic: a failed insert rolls the entire refresh back.
        with connection:
            for table in reversed(TABLES):
                connection.execute(f"DELETE FROM {table}")
            for table, columns in TABLES.items():
                names = ", ".join(columns)
                placeholders = ", ".join("?" for _ in columns)
                values = ([row[column] for column in columns] for row in data[table].values())
                connection.executemany(f"INSERT INTO {table} ({names}) VALUES ({placeholders})", values)
    return {table: len(rows) for table, rows in data.items()}


def metrics(database: Path) -> dict:
    query = (Path(__file__).parent.parent / "sql/metrics.sql").read_text(encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return dict(connection.execute(query).fetchone())
