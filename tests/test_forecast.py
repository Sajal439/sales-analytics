"""Forecast endpoint tests — Holt-Winters validation and Prophet fallback."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.category import Category
from app.models.product import Product
from app.models.sale import Sale


@pytest.fixture()
def forecast_db(db, test_user):
    """Seed enough data for forecasting (30+ days of daily sales)."""
    tenant_id = test_user["user_id"]
    cat = Category(name="ForecastCat", tenant_id=tenant_id)
    db.add(cat)
    db.flush()

    prod = Product(
        name="ForecastProduct", sku="FC-001", category_id=cat.id, tenant_id=tenant_id, unit_price=25.0
    )
    db.add(prod)
    db.flush()

    now = datetime.now(timezone.utc)
    for days_ago in range(60):
        sale = Sale(
            product_id=prod.id,
            tenant_id=tenant_id,
            quantity=2,
            total_amount=50.0,
            region="North",
            sale_date=now - timedelta(days=days_ago),
        )
        db.add(sale)

    db.commit()
    return db


class TestForecastEndpoint:
    def test_forecast_returns_correct_horizon(
        self, client, auth_headers, forecast_db
    ):
        """Forecast returns the requested number of data points."""
        response = client.get(
            "/forecast/revenue?horizon_days=7", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["horizon_days"] == 7
        assert len(data["forecast"]) == 7

    def test_forecast_non_negative(self, client, auth_headers, forecast_db):
        """All forecasted values are non-negative."""
        response = client.get(
            "/forecast/revenue?horizon_days=14", headers=auth_headers
        )
        assert response.status_code == 200
        for point in response.json()["forecast"]:
            assert point["predicted_revenue"] >= 0

    def test_forecast_has_method(self, client, auth_headers, forecast_db):
        """Response includes a method field."""
        response = client.get(
            "/forecast/revenue?horizon_days=7", headers=auth_headers
        )
        data = response.json()
        assert "method" in data
        assert data["method"] in (
            "prophet",
            "holt_winters",
            "holt_winters_fallback",
        )

    def test_backtest_endpoint(self, client, auth_headers, forecast_db):
        """Backtest endpoint returns MAPEs for Prophet and Holt-Winters."""
        response = client.get("/forecast/backtest?holdout_days=14", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["holdout_days"] == 14
        assert "prophet_mape" in data
        assert "holt_winters_mape" in data
        assert data["actual_revenue_sum"] > 0


class TestProphetFallback:
    def test_prophet_failure_triggers_fallback(
        self, client, auth_headers, forecast_db
    ):
        """When Prophet raises, the API falls back to Holt-Winters (not a 500)."""
        with patch(
            "app.services.forecasting._forecast_prophet",
            side_effect=RuntimeError("Prophet unavailable"),
        ):
            response = client.get(
                "/forecast/revenue?horizon_days=7", headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["method"] == "holt_winters_fallback"
            assert len(data["forecast"]) == 7
