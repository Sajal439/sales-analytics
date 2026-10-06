"""Analytics endpoint tests — seed a known dataset and assert exact numbers."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.category import Category
from app.models.product import Product
from app.models.sale import Sale


@pytest.fixture()
def seeded_db(db, test_user):
    """Seed a small, deterministic dataset for exact-value assertions."""
    tenant_id = test_user["user_id"]
    # Category
    cat = Category(name="TestCategory", tenant_id=tenant_id)
    db.add(cat)
    db.flush()

    # Product
    prod = Product(
        name="TestProduct", sku="TEST-001", category_id=cat.id, tenant_id=tenant_id, unit_price=10.0
    )
    db.add(prod)
    db.flush()

    # 5 sales over the last 10 days
    now = datetime.now(timezone.utc)
    sales_data = [
        # (days_ago, quantity, total_amount, region)
        (1, 2, 20.0, "North"),
        (2, 3, 30.0, "South"),
        (3, 1, 10.0, "North"),
        (5, 4, 40.0, "East"),
        (8, 5, 50.0, "North"),
    ]
    for days_ago, qty, amount, region in sales_data:
        sale = Sale(
            product_id=prod.id,
            tenant_id=tenant_id,
            quantity=qty,
            total_amount=amount,
            region=region,
            sale_date=now - timedelta(days=days_ago),
        )
        db.add(sale)

    db.commit()
    return db


class TestKPISummary:
    def test_kpi_values(self, client, auth_headers, seeded_db):
        """KPI summary returns correct totals for known data."""
        response = client.get(
            "/analytics/kpi-summary?days=30", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_revenue"] == 150.0
        assert data["total_orders"] == 5
        assert data["top_product"] == "TestProduct"
        assert data["top_region"] == "North"  # 3 sales in North = 80.0


class TestRevenueTrend:
    def test_trend_returns_data(self, client, auth_headers, seeded_db):
        """Revenue trend returns a non-empty list of data points."""
        response = client.get(
            "/analytics/revenue-trend?days=30", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        # Each point has date and revenue
        for point in data:
            assert "date" in point
            assert "revenue" in point

    def test_trend_anomaly_flag(self, client, auth_headers, seeded_db):
        """With flag_anomalies=true, anomaly field is present."""
        response = client.get(
            "/analytics/revenue-trend?days=30&flag_anomalies=true",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for point in data:
            assert "anomaly" in point


class TestTopProducts:
    def test_top_products_values(self, client, auth_headers, seeded_db):
        """Top products returns the correct product and totals."""
        response = client.get(
            "/analytics/top-products?days=30", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["product_name"] == "TestProduct"
        assert data[0]["total_revenue"] == 150.0
        assert data[0]["total_quantity"] == 15


class TestCategoryBreakdown:
    def test_category_breakdown(self, client, auth_headers, seeded_db):
        """Category breakdown shows 100% for the single test category."""
        response = client.get(
            "/analytics/category-breakdown?days=30", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["category"] == "TestCategory"
        assert data[0]["percentage"] == 100.0
