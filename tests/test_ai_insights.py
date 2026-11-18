"""Tests for the /ai/insights endpoint.

The Gemini API call is always mocked — these tests verify:
  1. Endpoint returns 200 and a valid schema when API key is set.
  2. Endpoint returns 200 with generated=False when API key is missing.
  3. Endpoint returns 200 with generated=False when Gemini raises.
  4. The context_snapshot always contains expected keys.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_minimal_sales(db):
    """Insert enough data for the analytics service to return non-empty results."""
    from datetime import datetime, timedelta, timezone

    from app.models.category import Category
    from app.models.product import Product
    from app.models.sale import Sale

    # Grab tenant from the user fixture — just use id=1 (first user)
    # Categories & products must belong to the same tenant.
    # We'll resolve tenant_id from the token in the test, so we just use 1.
    tenant_id = 1

    cat = Category(name="Electronics", tenant_id=tenant_id)
    db.add(cat)
    db.flush()

    prod = Product(name="Widget Pro", sku="WP-001", category_id=cat.id, tenant_id=tenant_id, unit_price=99.99)
    db.add(prod)
    db.flush()

    now = datetime.now(timezone.utc)
    for i in range(30):
        db.add(
            Sale(
                product_id=prod.id,
                tenant_id=tenant_id,
                quantity=2,
                total_amount=199.98,
                region="North",
                sale_date=now - timedelta(days=i),
            )
        )
    db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAIInsights:
    def test_returns_200_with_narrative_when_key_set(
        self, client: TestClient, auth_headers: dict, db
    ):
        """When API key is configured and Gemini succeeds, narrative is returned."""
        _seed_minimal_sales(db)

        mock_response = MagicMock()
        mock_response.text = "## Executive Summary\nSales look great.\n## Key Observations\n- Revenue is up.\n## Recommendations\n1. Keep going."

        with (
            patch("app.core.config.settings.GOOGLE_API_KEY", "fake-key-for-test"),
            patch("google.genai.Client") as mock_client_cls,
        ):
            mock_resp = MagicMock()
            mock_resp.text = mock_response.text
            mock_client_cls.return_value.models.generate_content.return_value = mock_resp

            resp = client.get("/ai/insights?days=30", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["generated"] is True
        assert body["narrative"] is not None
        assert "Executive Summary" in body["narrative"]
        assert body["reason"] is None
        assert "kpis" in body["context_snapshot"]

    def test_returns_200_with_fallback_when_no_key(
        self, client: TestClient, auth_headers: dict, db
    ):
        """When GOOGLE_API_KEY is not set, generated=False with a helpful reason."""
        _seed_minimal_sales(db)

        with patch("app.core.config.settings.GOOGLE_API_KEY", None):
            resp = client.get("/ai/insights?days=30", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["generated"] is False
        assert body["narrative"] is None
        assert "GOOGLE_API_KEY" in body["reason"]
        assert "context_snapshot" in body

    def test_returns_200_with_fallback_when_gemini_raises(
        self, client: TestClient, auth_headers: dict, db
    ):
        """When Gemini raises an exception, generated=False is returned (no 500)."""
        _seed_minimal_sales(db)

        with (
            patch("app.core.config.settings.GOOGLE_API_KEY", "fake-key-for-test"),
            patch("google.genai.Client") as mock_client_cls,
        ):
            mock_client_cls.return_value.models.generate_content.side_effect = RuntimeError(
                "quota exceeded"
            )
            resp = client.get("/ai/insights?days=30", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["generated"] is False
        assert "quota exceeded" in body["reason"]

    def test_context_snapshot_has_required_keys(
        self, client: TestClient, auth_headers: dict, db
    ):
        """context_snapshot always contains the expected analytics keys."""
        _seed_minimal_sales(db)

        with patch("app.core.config.settings.GOOGLE_API_KEY", None):
            resp = client.get("/ai/insights?days=30", headers=auth_headers)

        snapshot = resp.json()["context_snapshot"]
        for key in ("period_days", "kpis", "top_5_products", "category_breakdown", "anomaly_dates"):
            assert key in snapshot, f"Missing key: {key}"

    def test_requires_auth(self, client: TestClient):
        """Endpoint rejects unauthenticated requests."""
        resp = client.get("/ai/insights")
        assert resp.status_code == 401
