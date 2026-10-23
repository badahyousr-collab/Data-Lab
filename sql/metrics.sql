-- Позиция является единицей детализации. Группировка возвратов до join предотвращает
-- умножение продаж при нескольких возвратах одной позиции.
WITH completed_refunds AS (
  SELECT item_id, SUM(quantity) AS returned_qty, SUM(amount_cents) AS returned_cents
  FROM refunds WHERE status = 'completed' GROUP BY item_id
), item_net AS (
  SELECT o.order_id, o.customer_id, o.ordered_at, p.product_id, p.name, p.category,
         i.quantity - COALESCE(r.returned_qty, 0) AS net_units,
         i.quantity * i.unit_price_cents - COALESCE(r.returned_cents, 0) AS net_cents,
         i.quantity * i.unit_price_cents AS gross_cents,
         COALESCE(r.returned_cents, 0) AS refund_cents
  FROM order_items i JOIN orders o ON o.order_id = i.order_id
  JOIN products p ON p.product_id = i.product_id
  JOIN payments pay ON pay.order_id = o.order_id AND pay.status = 'captured'
  LEFT JOIN completed_refunds r ON r.item_id = i.item_id
), order_net AS (
  SELECT order_id, customer_id, SUM(net_cents) AS net_cents
  FROM item_net GROUP BY order_id, customer_id
), customer_purchases AS (
  SELECT customer_id, COUNT(*) AS purchase_count
  FROM order_net WHERE net_cents > 0 GROUP BY customer_id
)
SELECT
  (SELECT COALESCE(SUM(gross_cents), 0) FROM item_net) AS gross_cents,
  (SELECT COALESCE(SUM(refund_cents), 0) FROM item_net) AS refund_cents,
  (SELECT COALESCE(SUM(net_cents), 0) FROM item_net) AS revenue_cents,
  (SELECT COUNT(*) FROM order_net WHERE net_cents > 0) AS purchase_count,
  (SELECT COUNT(*) FROM customer_purchases WHERE purchase_count >= 2) AS repeat_customers;
