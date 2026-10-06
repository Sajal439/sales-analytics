"""Forecasting service — Prophet with Holt-Winters fallback.

The single entry point is `get_forecast()`. It tries Prophet first and
silently falls back to Holt-Winters on ANY failure (import error, runtime
error, insufficient data, etc.). A Prophet failure must NEVER become a 500.
"""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sale import Sale
from app.models.product import Product

logger = logging.getLogger(__name__)


def _daily_revenue_df(
    db: Session,
    tenant_id: int,
    product_id: int | None = None,
    category_id: int | None = None,
) -> pd.DataFrame:
    """Aggregate all historical sales into a daily revenue DataFrame.

    Returns a DataFrame with columns: ds (date), y (revenue).
    """
    query = (
        db.query(
            func.date(Sale.sale_date).label("ds"),
            func.sum(Sale.total_amount).label("y"),
        )
        .filter(Sale.tenant_id == tenant_id)
    )

    if product_id:
        query = query.filter(Sale.product_id == product_id)
    elif category_id:
        query = query.join(Product, Sale.product_id == Product.id).filter(
            Product.category_id == category_id
        )

    rows = (
        query.group_by(func.date(Sale.sale_date))
        .order_by(func.date(Sale.sale_date))
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=["ds", "y"])

    df = pd.DataFrame(rows, columns=["ds", "y"])
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = df["y"].astype(float)
    return df


def forecast_holt_winters(df: pd.DataFrame, horizon: int) -> list[dict]:
    """Holt-Winters exponential smoothing forecast.

    Returns a list of dicts with date, predicted_revenue, lower_bound,
    upper_bound (bounds are a simple ±10% estimate since Holt-Winters
    doesn't natively produce prediction intervals without simulation).
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    # Need at least 2 full seasonal periods for Holt-Winters
    seasonal_periods = 7  # weekly seasonality
    if len(df) < seasonal_periods * 2:
        # Fall back to simple trend extrapolation for very short series
        seasonal_periods = None

    try:
        if seasonal_periods:
            model = ExponentialSmoothing(
                df["y"].values,
                trend="add",
                seasonal="add",
                seasonal_periods=seasonal_periods,
            ).fit(optimized=True)
        else:
            model = ExponentialSmoothing(
                df["y"].values,
                trend="add",
            ).fit(optimized=True)

        predictions = model.forecast(horizon)
    except Exception:
        # Last resort — flat forecast at trailing 7-day mean
        logger.warning("Holt-Winters fit failed, using trailing mean fallback")
        mean_val = float(df["y"].tail(7).mean())
        predictions = [mean_val] * horizon

    last_date = df["ds"].max()
    result = []
    for i, val in enumerate(predictions):
        pred = max(float(val), 0.0)  # non-negative
        forecast_date = last_date + timedelta(days=i + 1)
        result.append({
            "date": forecast_date.date(),
            "predicted_revenue": round(pred, 2),
            "lower_bound": round(pred * 0.9, 2),
            "upper_bound": round(pred * 1.1, 2),
        })

    return result


def _forecast_prophet(df: pd.DataFrame, horizon: int) -> dict:
    """Try Prophet forecast. Raises on any failure (caller catches).

    Returns dict with method="prophet" and forecast list including
    Prophet's native uncertainty intervals.
    """
    from prophet import Prophet

    model = Prophet(
        weekly_seasonality=True,
        yearly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.95,
    )
    model.fit(df)

    future = model.make_future_dataframe(periods=horizon)
    prediction = model.predict(future)

    # Take only the forecast period (last `horizon` rows)
    forecast_rows = prediction.tail(horizon)

    forecast_list = []
    for _, row in forecast_rows.iterrows():
        pred = max(float(row["yhat"]), 0.0)
        forecast_list.append({
            "date": row["ds"].date(),
            "predicted_revenue": round(pred, 2),
            "lower_bound": round(max(float(row["yhat_lower"]), 0.0), 2),
            "upper_bound": round(max(float(row["yhat_upper"]), 0.0), 2),
        })

    return {
        "method": "prophet",
        "horizon_days": horizon,
        "forecast": forecast_list,
    }


def get_forecast(
    db: Session,
    tenant_id: int,
    horizon_days: int = 14,
    product_id: int | None = None,
    category_id: int | None = None,
) -> dict:
    """Single entry point for revenue forecasting.

    Tries Prophet first. On ANY failure, falls back to Holt-Winters.
    Never raises — always returns a valid forecast or an empty result.
    """
    horizon_days = min(max(horizon_days, 1), 90)

    df = _daily_revenue_df(db, tenant_id, product_id, category_id)
    if df.empty or len(df) < 7:
        return {
            "method": "insufficient_data",
            "horizon_days": horizon_days,
            "forecast": [],
        }

    # --- Try Prophet ---
    try:
        return _forecast_prophet(df, horizon_days)
    except Exception as e:
        logger.info(
            "Prophet unavailable or failed (%s), falling back to Holt-Winters",
            str(e),
        )

    # --- Holt-Winters fallback ---
    try:
        forecast_list = forecast_holt_winters(df, horizon_days)
        return {
            "method": "holt_winters_fallback",
            "horizon_days": horizon_days,
            "forecast": forecast_list,
        }
    except Exception as e:
        logger.error("Holt-Winters also failed: %s", str(e))
        return {
            "method": "error",
            "horizon_days": horizon_days,
            "forecast": [],
        }


def _calculate_mape(actuals: pd.Series, forecasts: pd.Series) -> float:
    mask = actuals != 0
    if not mask.any():
        return 0.0
    mape = (abs(actuals[mask] - forecasts[mask]) / actuals[mask]).mean() * 100
    return round(float(mape), 2)


def run_backtest(
    db: Session,
    tenant_id: int,
    holdout_days: int = 30,
    product_id: int | None = None,
    category_id: int | None = None,
) -> dict:
    """Run backtest for Prophet and Holt-Winters and return MAPE."""
    df = _daily_revenue_df(db, tenant_id, product_id, category_id)
    if len(df) < holdout_days + 14:
        return {"error": "Insufficient data for backtesting"}

    train_df = df.iloc[:-holdout_days].copy()
    test_df = df.iloc[-holdout_days:].copy()

    actuals = test_df["y"].values

    prophet_mape = None
    try:
        prophet_res = _forecast_prophet(train_df, holdout_days)
        prophet_preds = [row["predicted_revenue"] for row in prophet_res["forecast"]]
        prophet_mape = _calculate_mape(actuals, pd.Series(prophet_preds))
    except Exception as e:
        logger.warning(f"Prophet backtest failed: {e}")

    hw_mape = None
    try:
        hw_res = forecast_holt_winters(train_df, holdout_days)
        hw_preds = [row["predicted_revenue"] for row in hw_res]
        hw_mape = _calculate_mape(actuals, pd.Series(hw_preds))
    except Exception as e:
        logger.warning(f"Holt-Winters backtest failed: {e}")

    return {
        "holdout_days": holdout_days,
        "prophet_mape": prophet_mape,
        "holt_winters_mape": hw_mape,
        "actual_revenue_sum": round(float(actuals.sum()), 2),
        "test_period_start": test_df["ds"].iloc[0].date().isoformat(),
        "test_period_end": test_df["ds"].iloc[-1].date().isoformat(),
    }
