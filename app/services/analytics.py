"""Analytics service — revenue aggregation, KPIs, anomaly detection.

All heavy lifting uses Pandas for efficient in-memory aggregation on top of
SQLAlchemy queries. Routers should call these functions and return the result.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product
from app.models.sale import Sale


def _utcnow_naive() -> datetime:
    """UTC now without tzinfo — safe for Pandas comparisons with SQLite data.

    SQLite stores datetimes as strings and drops timezone info, so Pandas
    loads them as naive datetime64.  We strip tzinfo from our cutoffs to
    avoid 'Invalid comparison between dtype=datetime64 and datetime' errors.
    Postgres returns tz-aware datetimes, but naive comparisons still work
    there because Pandas will normalise both sides.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sales_df(db: Session, tenant_id: int, days: int) -> pd.DataFrame:
    """Query recent sales into a Pandas DataFrame.

    Returns columns: sale_date, total_amount, quantity, product_name,
    category_name, region.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            Sale.sale_date,
            Sale.total_amount,
            Sale.quantity,
            Sale.region,
            Product.name.label("product_name"),
            Category.name.label("category_name"),
        )
        .join(Product, Sale.product_id == Product.id)
        .join(Category, Product.category_id == Category.id)
        .filter(Sale.tenant_id == tenant_id)
        .filter(Sale.sale_date >= cutoff)
        .all()
    )
    if not rows:
        return pd.DataFrame(
            columns=[
                "sale_date",
                "total_amount",
                "quantity",
                "product_name",
                "category_name",
                "region",
            ]
        )
    df = pd.DataFrame(rows, columns=[
        "sale_date", "total_amount", "quantity",
        "region", "product_name", "category_name",
    ])
    # Normalise sale_date to naive datetime (handles SQLite naive + Postgres tz-aware)
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    if df["sale_date"].dt.tz is not None:
        df["sale_date"] = df["sale_date"].dt.tz_convert(None)
    return df


def get_kpi_summary(db: Session, tenant_id: int, days: int = 30) -> dict:
    """Total revenue, order count, growth %, top product, top region."""
    df = _sales_df(db, tenant_id, days)
    if df.empty:
        return {
            "total_revenue": 0.0,
            "total_orders": 0,
            "revenue_growth_pct": 0.0,
            "top_product": None,
            "top_region": None,
        }

    total_revenue = float(df["total_amount"].sum())
    total_orders = int(len(df))

    # Growth % vs prior period of the same length
    df_prior = _sales_df(db, tenant_id, days * 2)
    if not df_prior.empty:
        cutoff = _utcnow_naive() - timedelta(days=days)
        prior_revenue = float(
            df_prior[df_prior["sale_date"] < cutoff]["total_amount"].sum()
        )
        if prior_revenue > 0:
            revenue_growth_pct = round(
                ((total_revenue - prior_revenue) / prior_revenue) * 100, 2
            )
        else:
            revenue_growth_pct = 0.0
    else:
        revenue_growth_pct = 0.0

    # Top product by revenue
    top_product = (
        df.groupby("product_name")["total_amount"]
        .sum()
        .idxmax()
    )

    # Top region by revenue
    top_region = (
        df.groupby("region")["total_amount"]
        .sum()
        .idxmax()
    )

    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "revenue_growth_pct": revenue_growth_pct,
        "top_product": top_product,
        "top_region": top_region,
    }


def get_revenue_trend(
    db: Session,
    tenant_id: int,
    granularity: str = "daily",
    days: int = 90,
    flag_anomalies: bool = False,
) -> list[dict]:
    """Daily / weekly / monthly revenue time series.

    When flag_anomalies is True, marks points where revenue exceeds
    the 7-day rolling mean + 2 standard deviations.
    """
    df = _sales_df(db, tenant_id, days)
    if df.empty:
        return []

    df["date"] = pd.to_datetime(df["sale_date"]).dt.date

    if granularity == "weekly":
        df["date"] = pd.to_datetime(df["date"]) - pd.to_timedelta(
            pd.to_datetime(df["date"]).dt.dayofweek, unit="D"
        )
        df["date"] = df["date"].dt.date
    elif granularity == "monthly":
        df["date"] = pd.to_datetime(df["date"]).apply(
            lambda x: x.replace(day=1).date()
        )

    daily = df.groupby("date")["total_amount"].sum().reset_index()
    daily.columns = ["date", "revenue"]
    daily = daily.sort_values("date")

    result = []
    if flag_anomalies and len(daily) >= 7:
        rolling_mean = daily["revenue"].rolling(window=7, min_periods=1).mean()
        rolling_std = daily["revenue"].rolling(window=7, min_periods=1).std().fillna(0)
        threshold = rolling_mean + 2 * rolling_std
        for _, row in daily.iterrows():
            idx = row.name
            anomaly = bool(row["revenue"] > threshold.iloc[idx]) if idx < len(threshold) else False
            result.append({
                "date": row["date"],
                "revenue": round(float(row["revenue"]), 2),
                "anomaly": anomaly,
            })
    else:
        for _, row in daily.iterrows():
            result.append({
                "date": row["date"],
                "revenue": round(float(row["revenue"]), 2),
                "anomaly": None,
            })

    return result


def get_top_products(
    db: Session, tenant_id: int, limit: int = 10, days: int = 30
) -> list[dict]:
    """Products ranked by total revenue in the given period."""
    df = _sales_df(db, tenant_id, days)
    if df.empty:
        return []

    grouped = (
        df.groupby(["product_name", "category_name"])
        .agg(total_revenue=("total_amount", "sum"), total_quantity=("quantity", "sum"))
        .reset_index()
        .sort_values("total_revenue", ascending=False)
        .head(limit)
    )

    return [
        {
            "product_name": row["product_name"],
            "category": row["category_name"],
            "total_revenue": round(float(row["total_revenue"]), 2),
            "total_quantity": int(row["total_quantity"]),
        }
        for _, row in grouped.iterrows()
    ]


def get_category_breakdown(db: Session, tenant_id: int, days: int = 30) -> list[dict]:
    """Revenue share by category."""
    df = _sales_df(db, tenant_id, days)
    if df.empty:
        return []

    grouped = (
        df.groupby("category_name")["total_amount"]
        .sum()
        .reset_index()
        .sort_values("total_amount", ascending=False)
    )
    total = float(grouped["total_amount"].sum())

    return [
        {
            "category": row["category_name"],
            "revenue": round(float(row["total_amount"]), 2),
            "percentage": round(float(row["total_amount"]) / total * 100, 2)
            if total > 0
            else 0.0,
        }
        for _, row in grouped.iterrows()
    ]
