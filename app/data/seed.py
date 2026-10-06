"""Synthetic data seeder — generates ~18 months of realistic sales data.

Run as: python -m app.data.seed

Generates:
- 5 generic product categories
- ~20 products with realistic names, SKUs, and prices
- ~18 months of daily sales with patterns:
  - Gradual upward trend
  - Weekend spikes (higher footfall)
  - Festive-season bump (Nov-Dec holiday season)
  - Summer dip (Jul-Aug)
- A demo user: username=demo, password=demo1234
"""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone

from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.category import Category
from app.models.product import Product
from app.models.sale import Sale
from app.models.user import User

# ---------------------------------------------------------------------------
# Product catalogue — generic retail, usable by anyone
# ---------------------------------------------------------------------------

CATEGORIES_AND_PRODUCTS = {
    "Electronics": [
        ("Wireless Earbuds", "ELEC-001", 49.99),
        ("Bluetooth Speaker", "ELEC-002", 79.99),
        ("USB-C Hub", "ELEC-003", 34.99),
        ("Mechanical Keyboard", "ELEC-004", 129.99),
    ],
    "Home & Kitchen": [
        ("Blender Pro", "HOME-001", 59.99),
        ("Coffee Maker", "HOME-002", 89.99),
        ("Air Purifier", "HOME-003", 149.99),
        ("Smart Thermostat", "HOME-004", 199.99),
    ],
    "Clothing & Apparel": [
        ("Running Shoes", "CLTH-001", 99.99),
        ("Denim Jacket", "CLTH-002", 69.99),
        ("Polo Shirt", "CLTH-003", 29.99),
        ("Yoga Pants", "CLTH-004", 44.99),
    ],
    "Sports & Outdoors": [
        ("Yoga Mat", "SPRT-001", 24.99),
        ("Camping Tent", "SPRT-002", 189.99),
        ("Cycling Helmet", "SPRT-003", 59.99),
        ("Dumbbell Set", "SPRT-004", 79.99),
    ],
    "Books & Stationery": [
        ("Notebook Set", "BOOK-001", 14.99),
        ("Fountain Pen", "BOOK-002", 39.99),
        ("Desk Organizer", "BOOK-003", 27.99),
        ("Daily Planner", "BOOK-004", 19.99),
    ],
}

REGIONS = ["North", "South", "East", "West"]


def _seasonal_multiplier(day: datetime) -> float:
    """Return a multiplier based on time-of-year patterns.

    - Holiday season (Nov-Dec): ~1.4x boost
    - Summer dip (Jul-Aug): ~0.75x
    - Normal: 1.0x
    """
    month = day.month
    if month in (11, 12):
        return random.uniform(1.3, 1.5)
    if month in (7, 8):
        return random.uniform(0.7, 0.85)
    return random.uniform(0.9, 1.1)


def _weekend_multiplier(day: datetime) -> float:
    """Weekends see ~30% more traffic."""
    if day.weekday() >= 5:  # Saturday=5, Sunday=6
        return random.uniform(1.2, 1.4)
    return 1.0


def _import_real_data(db, file_path: str):
    """Import real data from JSON export."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read {file_path}: {e}")
        return

    # Basic implementation assuming JSON has a list of sales objects
    # This is a stub for the ETL payload shape.
    print(f"📥 Importing {len(data)} records from {file_path}...")
    
    # In a real scenario, we'd map categories/products based on the export.
    print("✅ Real data import logic scaffolded.")


def seed(source: str = "synthetic", file_path: str | None = None):
    """Main seeding function."""
    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if data already exists
        if db.query(Sale).first():
            print("⚠️  Data already exists — skipping seed. "
                  "Delete sales_analytics.db to re-seed.")
            return

        if source == "real":
            if not file_path:
                print("❌ Error: --file is required when --source=real")
                return
            _import_real_data(db, file_path)
            return

        # --- Demo user (Tenant) ---
        demo_user = User(
            username="demo",
            hashed_password=hash_password("demo1234"),
        )
        db.add(demo_user)
        db.flush()

        # --- Categories & Products ---
        products_by_id: list[tuple[Product, float]] = []

        for cat_name, items in CATEGORIES_AND_PRODUCTS.items():
            category = Category(name=cat_name, tenant_id=demo_user.id)
            db.add(category)
            db.flush()  # get category.id

            for prod_name, sku, price in items:
                product = Product(
                    name=prod_name,
                    sku=sku,
                    category_id=category.id,
                    tenant_id=demo_user.id,
                    unit_price=price,
                )
                db.add(product)
                db.flush()
                products_by_id.append((product, price))

        # Demo user is created above

        # --- Sales data: ~18 months ---
        end_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_date = end_date - timedelta(days=540)  # ~18 months

        total_sales = 0
        current_day = start_date

        # Gradual growth: base volume increases ~0.15% per day
        base_daily_orders = 15
        growth_per_day = 0.0015

        while current_day <= end_date:
            days_elapsed = (current_day - start_date).days

            # Daily order volume with trend, seasonal, and weekend effects
            trend_factor = 1 + (growth_per_day * days_elapsed)
            seasonal = _seasonal_multiplier(current_day)
            weekend = _weekend_multiplier(current_day)

            num_orders = int(
                base_daily_orders * trend_factor * seasonal * weekend
                + random.gauss(0, 2)
            )
            num_orders = max(num_orders, 3)  # at least a few sales per day

            for _ in range(num_orders):
                product, price = random.choice(products_by_id)
                quantity = random.choices(
                    [1, 2, 3, 4, 5],
                    weights=[40, 30, 15, 10, 5],
                    k=1,
                )[0]

                # Add small price variation (±5%)
                effective_price = price * random.uniform(0.95, 1.05)
                total_amount = round(quantity * effective_price, 2)

                sale = Sale(
                    product_id=product.id,
                    tenant_id=demo_user.id,
                    quantity=quantity,
                    total_amount=total_amount,
                    region=random.choice(REGIONS),
                    sale_date=current_day + timedelta(
                        hours=random.randint(8, 20),
                        minutes=random.randint(0, 59),
                    ),
                )
                db.add(sale)
                total_sales += 1

            current_day += timedelta(days=1)

        db.commit()
        print(f"✅ Seeded {len(CATEGORIES_AND_PRODUCTS)} categories, "
              f"{sum(len(v) for v in CATEGORIES_AND_PRODUCTS.values())} products, "
              f"and {total_sales:,} sales transactions.")
        print("👤 Demo user: username=demo, password=demo1234")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database.")
    parser.add_argument("--source", choices=["synthetic", "real"], default="synthetic", help="Data source type")
    parser.add_argument("--file", type=str, help="Path to JSON file (required if --source=real)")
    args = parser.parse_args()

    seed(source=args.source, file_path=args.file)
