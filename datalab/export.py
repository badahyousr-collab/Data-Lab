"""Export synthetic per-item order facts for the public, read-only site."""

import json
import sqlite3
from pathlib import Path


QUERY = """
WITH r AS (
  SELECT item_id, SUM(quantity) AS qty, SUM(amount_cents) AS cents
  FROM refunds WHERE status = 'completed' GROUP BY item_id
)
SELECT o.order_id, o.customer_id, o.ordered_at, p.name, p.category,
       i.quantity AS gross_units, i.quantity * i.unit_price_cents AS gross_cents,
       COALESCE(r.qty, 0) AS refunded_units, COALESCE(r.cents, 0) AS refund_cents
FROM order_items i JOIN orders o ON o.order_id = i.order_id
JOIN products p ON p.product_id = i.product_id
JOIN payments pay ON pay.order_id = o.order_id AND pay.status = 'captured'
LEFT JOIN r ON r.item_id = i.item_id ORDER BY o.ordered_at, o.order_id, i.item_id
"""


def export(database: Path, output: Path) -> int:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(QUERY)]
    payload = {"title": "pipisso Data Lab", "currency": "RUB", "synthetic": True,
               "date_basis": "Дата исходного заказа, UTC", "rows": rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(rows)
