"""Sales and products router — paginated sales, product catalogue."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.category import Category
from app.models.product import Product
from app.models.sale import Sale
from app.schemas.sales import ProductResponse, SaleListResponse, SaleResponse, IngestRequest

router = APIRouter(tags=["Sales & Products"], dependencies=[Depends(decode_token)])


@router.get("/sales", response_model=SaleListResponse)
def list_sales(
    product: str | None = Query(None, description="Filter by product name (partial match)"),
    region: str | None = Query(None, description="Filter by region"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Paginated list of sales with optional filters."""
    query = (
        db.query(Sale, Product.name.label("product_name"), Category.name.label("category_name"))
        .join(Product, Sale.product_id == Product.id)
        .join(Category, Product.category_id == Category.id)
        .filter(Sale.tenant_id == tenant_id)
    )

    if product:
        query = query.filter(Product.name.ilike(f"%{product}%"))
    if region:
        query = query.filter(Sale.region.ilike(f"%{region}%"))

    total = query.count()
    rows = (
        query.order_by(Sale.sale_date.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    sales = [
        SaleResponse(
            id=sale.id,
            product_name=product_name,
            category=category_name,
            quantity=sale.quantity,
            total_amount=sale.total_amount,
            region=sale.region,
            sale_date=sale.sale_date,
        )
        for sale, product_name, category_name in rows
    ]

    return SaleListResponse(sales=sales, total=total, page=page, per_page=per_page)


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Full product catalogue."""
    rows = (
        db.query(Product, Category.name.label("category_name"))
        .join(Category, Product.category_id == Category.id)
        .filter(Product.tenant_id == tenant_id)
        .order_by(Product.name)
        .all()
    )
    return [
        ProductResponse(
            id=product.id,
            name=product.name,
            sku=product.sku,
            category=category_name,
            unit_price=product.unit_price,
        )
        for product, category_name in rows
    ]


@router.post("/ingest", response_model=dict)
def ingest_sales(
    payload: IngestRequest,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(decode_token),
):
    """Batch ingest sales data from an external system (e.g. Node.js backend)."""
    inserted = 0

    # Cache categories and products to avoid excessive DB queries
    categories = {c.name: c for c in db.query(Category).filter(Category.tenant_id == tenant_id).all()}
    products = {p.sku: p for p in db.query(Product).filter(Product.tenant_id == tenant_id).all()}

    for item in payload.sales:
        # Upsert category
        category = categories.get(item.category_name)
        if not category:
            category = Category(name=item.category_name, tenant_id=tenant_id)
            db.add(category)
            db.flush()
            categories[item.category_name] = category

        # Upsert product
        product = products.get(item.product_sku)
        if not product:
            unit_price = item.total_amount / item.quantity if item.quantity > 0 else 0
            product = Product(
                name=item.product_name,
                sku=item.product_sku,
                category_id=category.id,
                tenant_id=tenant_id,
                unit_price=unit_price
            )
            db.add(product)
            db.flush()
            products[item.product_sku] = product

        # Insert sale
        sale = Sale(
            product_id=product.id,
            tenant_id=tenant_id,
            quantity=item.quantity,
            total_amount=item.total_amount,
            region=item.region,
            sale_date=item.sale_date,
        )
        db.add(sale)
        inserted += 1

    db.commit()
    return {"message": "Ingest successful", "inserted_count": inserted}
