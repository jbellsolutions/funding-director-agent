#!/usr/bin/env python3
"""Validate product and destination policy before any live funding action."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "files" / "local-packages" / "funding-director" / "src"
sys.path.insert(0, str(CORE_SRC))

from funding_director.catalog import ProductCatalog  # noqa: E402
from funding_director.destinations import DestinationCatalog  # noqa: E402
from funding_director.models import ProductStatus, ValidationError  # noqa: E402


def validate(products_path: Path, destinations_path: Path) -> tuple[list[str], list[str]]:
    products = ProductCatalog(products_path)
    destinations = DestinationCatalog(destinations_path)
    errors: list[str] = []
    warnings: list[str] = []
    active_destinations = [item for item in destinations.destinations if item.status == "active"]

    for product in products.products:
        if product.status is not ProductStatus.ACTIVE:
            continue
        routes = [
            item for item in active_destinations
            if product.product_id in item.product_ids and item.adapter == product.submission_adapter
        ]
        if not routes:
            errors.append(
                f"{product.product_id}: active Product Card has no matching active destination"
            )
        if product.expires_at and date.fromisoformat(product.expires_at) <= date.today() + timedelta(days=30):
            warnings.append(f"{product.product_id}: provider evidence expires within 30 days")

    product_ids = {item.product_id for item in products.products}
    for destination in active_destinations:
        unknown = sorted(set(destination.product_ids) - product_ids)
        if unknown:
            errors.append(
                f"{destination.destination_id}: destination references unknown products: {', '.join(unknown)}"
            )
        if destination.adapter == "http_json" and not destination.url.startswith("https://"):
            errors.append(f"{destination.destination_id}: active HTTP route must use HTTPS")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_config = ROOT / "files" / "local-packages" / "funding-director" / "config"
    parser.add_argument("--products", type=Path, default=default_config / "products.json")
    parser.add_argument("--destinations", type=Path, default=default_config / "destinations.json")
    args = parser.parse_args()
    try:
        errors, warnings = validate(args.products, args.destinations)
    except (OSError, ValueError, ValidationError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for message in errors:
            print(f"INVALID: {message}", file=sys.stderr)
        return 1
    print("Funding configuration is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
