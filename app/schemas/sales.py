"""Sales and product response schemas."""

from datetime import datetime

from pydantic import BaseModel


class SaleResponse(BaseModel):
    """Single sale transaction."""

    id: int
    product_name: str
    category: str
    quantity: int
    total_amount: float
    region: str
    sale_date: datetime

    model_config = {"from_attributes": True}


class SaleListResponse(BaseModel):
    """Paginated list of sales."""

    sales: list[SaleResponse]
    total: int
    page: int
    per_page: int


class ProductResponse(BaseModel):
    """Product catalogue entry."""

    id: int
    name: str
    sku: str
    category: str
    unit_price: float

    model_config = {"from_attributes": True}


class SaleCreate(BaseModel):
    """Payload for creating a single sale via ingest."""
    product_sku: str
    product_name: str
    category_name: str
    quantity: int
    total_amount: float
    region: str
    sale_date: datetime


class IngestRequest(BaseModel):
    """Payload for batch ingesting sales."""
    sales: list[SaleCreate]
