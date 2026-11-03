"""Deterministic sample raw CSVs for the local ETL demo.

The generated files mirror the Olist schemas consumed by ``etl/extract.py`` and
``etl/transform.py``, including consistent foreign keys so the referential
integrity step keeps rows instead of silently dropping them.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .config import FILE_PATHS, RAW_DATA_DIR, logger

SAMPLE_FILENAMES = (
    "olist_geolocation_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_products_dataset.csv",
    "product_category_name_translation.csv",
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_payments_dataset.csv",
    "olist_reviews_dataset.csv",
)

_CATEGORIES = {
    "beleza_saude": "health_beauty",
    "informatica_acessorios": "computers_accessories",
    "moveis_decoracao": "furniture_decor",
    "esporte_lazer": "sports_leisure",
    "utilidades_domesticas": "housewares",
    "relogios_presentes": "watches_gifts",
    "telefonia": "telephony",
    "brinquedos": "toys",
}

_CITIES = {
    "SP": "sao paulo",
    "RJ": "rio de janeiro",
    "MG": "belo horizonte",
    "RS": "porto alegre",
    "PR": "curitiba",
    "SC": "florianopolis",
}

_PAYMENT_TYPES = ("credit_card", "boleto", "voucher", "debit_card", "pix")


def _timestamp(base: datetime, days: int, seconds: int) -> str:
    return (base + timedelta(days=days, seconds=seconds)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def build_sample_frames(
    seed: int = 7, order_multiplier: float = 1.0
) -> Dict[str, pd.DataFrame]:
    """Return deterministic raw frames keyed like ``etl.config.FILE_PATHS``.

    ``seed`` and ``order_multiplier`` let the Data Studio regenerate a fresh
    dataset with a different size and distribution while keeping every call
    reproducible for the same pair of arguments.
    """

    rng = random.Random(seed)
    base = datetime(2024, 1, 1, 8, 0, 0)

    multiplier = max(0.25, float(order_multiplier))
    n_orders = max(30, int(round(90 * multiplier)))
    n_customers = max(20, int(round(n_orders * 0.85)))
    n_reviews = min(n_orders, max(10, int(round(n_orders * 0.85))))
    day_step = max(1, int(round(760 / max(1, n_orders))))

    states = list(_CITIES)
    zip_prefixes = [1001 + index * 137 for index in range(20)]

    geolocation = pd.DataFrame(
        {
            "geolocation_zip_code_prefix": zip_prefixes,
            "geolocation_lat": [round(-23.5 + rng.uniform(-6, 6), 6) for _ in zip_prefixes],
            "geolocation_lng": [round(-46.6 + rng.uniform(-6, 6), 6) for _ in zip_prefixes],
            "geolocation_city": [
                _CITIES[states[index % len(states)]] for index in range(20)
            ],
            "geolocation_state": [states[index % len(states)] for index in range(20)],
        }
    )

    customer_ids = [f"cust_{index:04d}" for index in range(n_customers)]
    customers = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "customer_unique_id": [f"uniq_{index:04d}" for index in range(n_customers)],
            "customer_zip_code_prefix": [
                zip_prefixes[index % len(zip_prefixes)] for index in range(n_customers)
            ],
            "customer_city": [
                _CITIES[states[index % len(states)]] for index in range(n_customers)
            ],
            "customer_state": [states[index % len(states)] for index in range(n_customers)],
        }
    )

    n_sellers = 10
    seller_ids = [f"seller_{index:02d}" for index in range(n_sellers)]
    sellers = pd.DataFrame(
        {
            "seller_id": seller_ids,
            "seller_zip_code_prefix": [
                zip_prefixes[index % len(zip_prefixes)] for index in range(n_sellers)
            ],
            "seller_city": [
                _CITIES[states[index % len(states)]] for index in range(n_sellers)
            ],
            "seller_state": [states[index % len(states)] for index in range(n_sellers)],
        }
    )

    n_products = 24
    product_ids = [f"prod_{index:03d}" for index in range(n_products)]
    category_keys = list(_CATEGORIES)
    products = pd.DataFrame(
        {
            "product_id": product_ids,
            "product_category_name": [
                category_keys[index % len(category_keys)] for index in range(n_products)
            ],
            "product_name_lenght": [rng.randint(20, 60) for _ in range(n_products)],
            "product_description_lenght": [
                rng.randint(80, 500) for _ in range(n_products)
            ],
            "product_photos_qty": [rng.randint(1, 5) for _ in range(n_products)],
            "product_weight_g": [rng.randint(200, 9000) for _ in range(n_products)],
            "product_length_cm": [rng.randint(10, 60) for _ in range(n_products)],
            "product_height_cm": [rng.randint(5, 40) for _ in range(n_products)],
            "product_width_cm": [rng.randint(8, 45) for _ in range(n_products)],
        }
    )

    category_translation = pd.DataFrame(
        {
            "product_category_name": list(_CATEGORIES),
            "product_category_name_english": list(_CATEGORIES.values()),
        }
    )

    order_ids = [f"order_{index:04d}" for index in range(n_orders)]
    orders = pd.DataFrame(
        {
            "order_id": order_ids,
            "customer_id": [customer_ids[index % n_customers] for index in range(n_orders)],
            "order_status": [
                "delivered" if index % 10 else "shipped" for index in range(n_orders)
            ],
            "order_purchase_timestamp": [
                _timestamp(base, index * day_step, rng.randint(0, 86400)) for index in range(n_orders)
            ],
            "order_approved_at": [
                _timestamp(base, index * day_step, rng.randint(0, 86400)) for index in range(n_orders)
            ],
            "order_delivered_carrier_date": [
                _timestamp(base, index * day_step + 1, rng.randint(0, 86400))
                for index in range(n_orders)
            ],
            "order_delivered_customer_date": [
                _timestamp(base, index * day_step + rng.randint(3, 12), rng.randint(0, 86400))
                for index in range(n_orders)
            ],
            "order_estimated_delivery_date": [
                _timestamp(base, index * day_step + 15, 0) for index in range(n_orders)
            ],
        }
    )

    order_items_rows: List[dict] = []
    for index in range(n_orders):
        items = 1 if index % 4 else 2
        for item_index in range(items):
            order_items_rows.append(
                {
                    "order_id": order_ids[index],
                    "order_item_id": item_index + 1,
                    "product_id": product_ids[(index + item_index) % n_products],
                    "seller_id": seller_ids[(index + item_index) % n_sellers],
                    "shipping_limit_date": _timestamp(
                        base, index * day_step + 2, rng.randint(0, 86400)
                    ),
                    "price": round(rng.uniform(19.9, 420.0), 2),
                    "freight_value": round(rng.uniform(6.0, 42.0), 2),
                }
            )
    order_items = pd.DataFrame(order_items_rows)

    payment_rows = []
    for index in range(n_orders):
        payment_type = _PAYMENT_TYPES[index % len(_PAYMENT_TYPES)]
        payment_rows.append(
            {
                "order_id": order_ids[index],
                "payment_sequential": 1,
                "payment_type": payment_type,
                "payment_installments": rng.randint(1, 6),
                "payment_value": round(rng.uniform(25.0, 520.0), 2),
            }
        )
        if index % 9 == 0:
            payment_rows.append(
                {
                    "order_id": order_ids[index],
                    "payment_sequential": 2,
                    "payment_type": "voucher",
                    "payment_installments": 1,
                    "payment_value": round(rng.uniform(5.0, 60.0), 2),
                }
            )
    payments = pd.DataFrame(payment_rows)

    review_rows = []
    for index in range(n_reviews):
        has_comment = index % 3 != 0
        review_rows.append(
            {
                "review_id": f"review_{index:03d}",
                "order_id": order_ids[index],
                "review_score": rng.choices(
                    [1, 2, 3, 4, 5], weights=[6, 5, 8, 22, 59]
                )[0],
                "review_comment_title": "Delivery" if has_comment else None,
                "review_comment_message": (
                    "Arrived on time and well packed." if has_comment else None
                ),
                "review_creation_date": _timestamp(
                    base, index * day_step + 13, rng.randint(0, 86400)
                ),
                "review_answer_timestamp": _timestamp(
                    base, index * day_step + 14, rng.randint(0, 86400)
                ),
            }
        )
    reviews = pd.DataFrame(review_rows)

    return {
        "geolocation": geolocation,
        "customers": customers,
        "sellers": sellers,
        "products": products,
        "category_translation": category_translation,
        "orders": orders,
        "order_items": order_items,
        "payments": payments,
        "reviews": reviews,
    }


def seed_sample_raw_csvs(
    raw_dir: Optional[Path] = None,
    overwrite: bool = False,
    seed: int = 7,
    order_multiplier: float = 1.0,
) -> Dict[str, object]:
    """Write valid sample CSVs into ``data/raw`` when they are missing.

    Existing files are never overwritten unless ``overwrite=True``, so a real
    Olist dataset is left untouched. ``seed`` and ``order_multiplier`` produce
    a freshly randomised dataset with a different size and distribution.
    Returns a summary suitable for display in the Data Studio.
    """

    target = Path(raw_dir) if raw_dir else Path(RAW_DATA_DIR)
    target.mkdir(parents=True, exist_ok=True)

    frames = build_sample_frames(seed=seed, order_multiplier=order_multiplier)
    created: List[str] = []
    skipped: List[str] = []
    rows: Dict[str, int] = {}

    for name, frame in frames.items():
        filename = Path(FILE_PATHS[name]).name
        path = target / filename
        rows[name] = int(len(frame))

        if path.exists() and not overwrite:
            skipped.append(filename)
            continue

        frame.to_csv(path, index=False, encoding="utf-8")
        created.append(filename)
        logger.info("Wrote sample CSV %s (%d rows).", path, len(frame))

    return {
        "raw_dir": str(target),
        "created": created,
        "skipped": skipped,
        "rows": rows,
        "total_files": len(frames),
        "seed": seed,
        "order_multiplier": order_multiplier,
        "total_orders": int(rows.get("orders", 0)),
    }
