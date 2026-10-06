"""Analytics response schemas."""

from datetime import date

from pydantic import BaseModel


class KPISummary(BaseModel):
    """Key performance indicators for a given period."""

    total_revenue: float
    total_orders: int
    revenue_growth_pct: float
    top_product: str | None
    top_region: str | None


class RevenueTrendPoint(BaseModel):
    """Single data point in a revenue time series."""

    date: date
    revenue: float
    anomaly: bool | None = None


class TopProduct(BaseModel):
    """Product ranked by revenue."""

    product_name: str
    category: str
    total_revenue: float
    total_quantity: int


class CategoryBreakdown(BaseModel):
    """Revenue share for a single category."""

    category: str
    revenue: float
    percentage: float
