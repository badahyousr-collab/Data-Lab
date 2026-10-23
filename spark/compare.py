"""Compare PySpark results to the SQL pipeline on the same validated CSV snapshot.

Run `python -m spark.compare --input data/demo --database data/sales.db` after
installing optional requirements. Times include reads and transformation, not
Python/Spark installation. Spark startup is reported separately.
"""

import argparse
import json
import time
from pathlib import Path

from datalab.pipeline import metrics, read_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/demo"))
    parser.add_argument("--database", type=Path, default=Path("data/sales.db"))
    args = parser.parse_args()
    read_snapshot(args.input)  # Same contract and error handling as the SQL loader.
    sql_start = time.perf_counter()
    expected = metrics(args.database)
    sql_seconds = time.perf_counter() - sql_start

    try:
        from pyspark.sql import SparkSession, functions as F
    except ImportError as exc:
        parser.error("PySpark missing: pip install -r requirements-spark.txt")
    start = time.perf_counter()
    spark = SparkSession.builder.master("local[*]").appName("pipisso-data-lab").getOrCreate()
    startup_seconds = time.perf_counter() - start
    try:
        start = time.perf_counter()
        def csv(name):
            return spark.read.option("header", True).option("inferSchema", True).csv(str(args.input / f"{name}.csv"))

        orders = csv("orders").select("order_id", "customer_id")
        items = csv("order_items")
        paid = csv("payments").filter(F.col("status") == "captured").select("order_id")
        refunds = (csv("refunds").filter(F.col("status") == "completed")
                   .groupBy("item_id")
                   .agg(F.sum("quantity").alias("returned_qty"), F.sum("amount_cents").alias("returned_cents")))
        item_net = (items.join(orders, "order_id").join(paid, "order_id")
                    .join(refunds, "item_id", "left")
                    .withColumn("gross_cents", F.col("quantity") * F.col("unit_price_cents"))
                    .withColumn("refund_cents", F.coalesce(F.col("returned_cents"), F.lit(0)))
                    .withColumn("net_cents", F.col("gross_cents") - F.col("refund_cents"))
                    .cache())
        total = item_net.agg(F.sum("gross_cents"), F.sum("refund_cents"), F.sum("net_cents")).first()
        purchases = (item_net.groupBy("order_id", "customer_id").agg(F.sum("net_cents").alias("net"))
                     .filter(F.col("net") > 0).cache())
        per_customer = purchases.groupBy("customer_id").count()
        actual = {"gross_cents": total[0] or 0, "refund_cents": total[1] or 0,
                  "revenue_cents": total[2] or 0, "purchase_count": purchases.count(),
                  "repeat_customers": per_customer.filter(F.col("count") >= 2).count()}
        spark_seconds = time.perf_counter() - start
        print(json.dumps({"sql": expected, "spark": actual, "equal": actual == expected,
                          "sql_query_seconds": round(sql_seconds, 3),
                          "spark_startup_seconds": round(startup_seconds, 3),
                          "spark_processing_seconds": round(spark_seconds, 3)}, ensure_ascii=False))
        if actual != expected:
            raise SystemExit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
