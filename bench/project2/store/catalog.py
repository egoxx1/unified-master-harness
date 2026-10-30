import csv
from pathlib import Path

from .money import to_cents

PRODUCTS = Path(__file__).resolve().parent.parent / "data" / "products.csv"


def load_catalog(path=PRODUCTS):
    """Read a products CSV (sku,name,price) into {sku: {"name": ..., "price": cents}}."""
    with open(path, newline="") as f:
        return {row["sku"]: {"name": row["name"], "price": to_cents(row["price"])} for row in csv.DictReader(f)}
