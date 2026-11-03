"""Deterministic, data-driven analyst used when Gemini is unavailable.

Every function here reads the *actual* filtered dashboard frames, so the AI tab
keeps producing meaningful business analysis when the API key is missing, the
quota is exhausted, or the network is offline. Nothing in this module raises for
partial or empty data; it degrades to a short explanatory line instead.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

import pandas as pd


# --------------------------------------------------------------------------- #
# Small, defensive helpers
# --------------------------------------------------------------------------- #


def _frame(value: Any) -> pd.DataFrame:
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def _text(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype="object")
    return frame[column].dropna().astype(str).str.strip()


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _ratio(part: float, whole: float) -> float:
    return float(part) / float(whole) if whole else 0.0


def _weighted_rating(review_df: pd.DataFrame) -> float:
    scores = _numeric(review_df, "average_score")
    if scores.empty:
        return 0.0

    if "review_count" in review_df.columns:
        counts = pd.to_numeric(review_df["review_count"], errors="coerce")
        common = scores.index.intersection(counts.dropna().index)
        if len(common):
            weights = counts.loc[common].clip(lower=1)
            if weights.sum() > 0:
                return float((scores.loc[common] * weights).sum() / weights.sum())

    return float(scores.mean())


def _monthly_revenue(sales_df: pd.DataFrame, limit: int = 6) -> List[Dict[str, Any]]:
    if sales_df.empty or "order_purchase_timestamp" not in sales_df.columns:
        return []

    dates = pd.to_datetime(sales_df["order_purchase_timestamp"], errors="coerce")
    values = pd.to_numeric(sales_df.get("total_order_value"), errors="coerce")
    if values is None:
        return []

    frame = pd.DataFrame({"month": dates.dt.strftime("%Y-%m"), "revenue": values})
    frame = frame.dropna(subset=["month"])
    if frame.empty:
        return []

    grouped = frame.groupby("month", sort=True)["revenue"].sum().tail(limit)
    return [
        {"month": str(month), "revenue": round(float(value), 2)}
        for month, value in grouped.items()
    ]


def _top_breakdown(
    frame: pd.DataFrame, key: str, value: str, limit: int = 5
) -> List[Dict[str, Any]]:
    if frame.empty or key not in frame.columns or value not in frame.columns:
        return []

    working = frame[[key, value]].copy()
    working[value] = pd.to_numeric(working[value], errors="coerce")
    working = working.dropna()
    if working.empty:
        return []

    grouped = (
        working.groupby(key, sort=False)[value]
        .sum()
        .sort_values(ascending=False)
        .head(limit)
    )
    total = float(working[value].sum())
    return [
        {
            "label": str(label),
            "value": round(float(magnitude), 2),
            "share": _ratio(magnitude, total),
        }
        for label, magnitude in grouped.items()
    ]


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #


def compute_metrics(
    sales_df: Any,
    customer_df: Any,
    product_df: Any,
    payment_df: Any,
    review_df: Any,
) -> Dict[str, Any]:
    """Return a compact, JSON-safe KPI snapshot for prompts and fallbacks."""

    sales = _frame(sales_df)
    customers = _frame(customer_df)
    products = _frame(product_df)
    payments = _frame(payment_df)
    reviews = _frame(review_df)

    revenue = float(_numeric(sales, "total_order_value").sum())
    orders = (
        int(sales["order_id"].nunique())
        if "order_id" in sales.columns
        else int(len(sales))
    )

    unique_customers = (
        int(customers["customer_unique_id"].nunique())
        if "customer_unique_id" in customers.columns
        else int(len(customers))
    )

    lifetime_orders = _numeric(customers, "lifetime_orders")
    repeat_ratio = _ratio((lifetime_orders > 1).sum(), len(lifetime_orders))
    average_lifetime_spend = float(_numeric(customers, "lifetime_spent").mean() or 0.0)

    rating = _weighted_rating(reviews)
    scores = _numeric(reviews, "average_score")
    negative_share = _ratio((scores <= 2.5).sum(), len(scores))

    state_source = sales if "customer_state" in sales.columns else customers
    states = _text(state_source, "customer_state")
    cities = _text(state_source, "customer_city")
    top_state = str(states.value_counts().index[0]) if not states.empty else ""
    top_state_share = _ratio(states.value_counts().iloc[0], len(states)) if not states.empty else 0.0
    top_city = str(cities.value_counts().index[0]) if not cities.empty else ""

    categories = _top_breakdown(products, "category_name", "total_category_revenue")
    units_sold = float(_numeric(products, "total_units_sold").sum())
    state_breakdown = _top_breakdown(sales, "customer_state", "total_order_value")

    payment_types = _top_breakdown(payments, "payment_type", "total_volume")
    payment_volume = float(_numeric(payments, "total_volume").sum())

    monthly = _monthly_revenue(sales)
    momentum = 0.0
    if len(monthly) >= 2 and monthly[-2]["revenue"]:
        momentum = (
            monthly[-1]["revenue"] - monthly[-2]["revenue"]
        ) / monthly[-2]["revenue"]

    return {
        "revenue": revenue,
        "orders": orders,
        "average_order_value": revenue / orders if orders else 0.0,
        "unique_customers": unique_customers,
        "repeat_ratio": repeat_ratio,
        "average_lifetime_spend": average_lifetime_spend,
        "rating": rating,
        "negative_review_share": negative_share,
        "reviewed_orders": int(len(scores)),
        "top_state": top_state,
        "top_state_share": top_state_share,
        "top_city": top_city,
        "state_count": int(states.nunique()),
        "city_count": int(cities.nunique()),
        "top_categories": categories,
        "category_count": int(products["category_name"].nunique())
        if "category_name" in products.columns
        else 0,
        "units_sold": units_sold,
        "state_breakdown": state_breakdown,
        "payment_types": payment_types,
        "payment_volume": payment_volume,
        "monthly_revenue": monthly,
        "momentum": momentum,
        "rows": {
            "sales": int(len(sales)),
            "customers": int(len(customers)),
            "products": int(len(products)),
            "payments": int(len(payments)),
            "reviews": int(len(reviews)),
        },
    }


def business_health(metrics: Dict[str, Any]) -> tuple[int, str]:
    """Blend satisfaction, retention, pricing, and momentum into 0-100."""

    score = 62.0
    score += min(12.0, float(metrics.get("repeat_ratio") or 0.0) * 30.0)

    rating = float(metrics.get("rating") or 0.0)
    score += (rating / 5.0) * 18.0 if rating else 6.0

    score -= float(metrics.get("negative_review_share") or 0.0) * 25.0

    aov = float(metrics.get("average_order_value") or 0.0)
    if aov >= 120:
        score += 5.0
    elif aov >= 60:
        score += 3.0

    momentum = float(metrics.get("momentum") or 0.0)
    if momentum > 0.05:
        score += 4.0
    elif momentum < -0.05:
        score -= 4.0

    bounded = int(max(5, min(99, round(score))))
    if bounded >= 85:
        label = "Excellent"
    elif bounded >= 72:
        label = "Strong"
    elif bounded >= 60:
        label = "Healthy"
    elif bounded >= 45:
        label = "Watch list"
    else:
        label = "At risk"
    return bounded, label


# --------------------------------------------------------------------------- #
# Narrative sections
# --------------------------------------------------------------------------- #


def executive_summary(metrics: Dict[str, Any]) -> str:
    score, label = business_health(metrics)

    if metrics.get("momentum"):
        trend = (
            f"Revenue is {'up' if metrics['momentum'] >= 0 else 'down'} "
            f"{abs(metrics['momentum']) * 100:.1f}% month over month."
        )
    else:
        trend = "Not enough dated history to compute a month-over-month trend."

    lines = [
        f"**Business health index: {score}/100 — {label}.**",
        "",
        (
            f"- **Revenue:** {_money(metrics['revenue'])} across "
            f"{metrics['orders']:,} orders "
            f"(AOV {_money(metrics['average_order_value'])})."
        ),
        (
            f"- **Customers:** {metrics['unique_customers']:,} unique buyers, "
            f"{_pct(metrics['repeat_ratio'])} repeat, "
            f"average lifetime spend {_money(metrics['average_lifetime_spend'])}."
        ),
        (
            f"- **Satisfaction:** {metrics['rating']:.2f}/5 from "
            f"{metrics['reviewed_orders']:,} reviewed orders; "
            f"{_pct(metrics['negative_review_share'])} scored 2.5 or lower."
        ),
        f"- **Momentum:** {trend}",
    ]

    if metrics.get("top_categories"):
        leader = metrics["top_categories"][0]
        lines.append(
            f"- **Product mix:** {leader['label']} leads with "
            f"{_money(leader['value'])} ({_pct(leader['share'])} of category revenue)."
        )

    if metrics.get("top_state"):
        lines.append(
            f"- **Geography:** {metrics['top_state']} is the largest market "
            f"({_pct(metrics['top_state_share'])} of rows), ahead of "
            f"{metrics['state_count']} states and {metrics['city_count']} cities."
        )

    return "\n".join(lines)


def sales_insights(metrics: Dict[str, Any]) -> str:
    if not metrics.get("orders"):
        return "No sales rows are available in the active filter window."

    lines = [
        (
            f"Revenue reached {_money(metrics['revenue'])} from "
            f"{metrics['orders']:,} orders at an average order value of "
            f"{_money(metrics['average_order_value'])}."
        )
    ]

    if metrics.get("monthly_revenue"):
        current = metrics["monthly_revenue"][-1]
        lines.append(
            f"The most recent active month ({current['month']}) produced "
            f"{_money(current['revenue'])}."
        )

    if metrics.get("momentum"):
        direction = "expansion" if metrics["momentum"] >= 0 else "contraction"
        lines.append(
            f"Month-over-month {direction} of "
            f"{abs(metrics['momentum']) * 100:.1f}% suggests "
            f"{'durable demand' if metrics['momentum'] >= 0 else 'a demand soft patch'}"
            " that should be confirmed against the next cycle."
        )

    if metrics.get("top_state"):
        lines.append(
            f"{metrics['top_state']} contributes "
            f"{_pct(metrics['top_state_share'])} of order rows, making it the "
            "highest-leverage market for local campaigns."
        )

    if metrics.get("average_order_value") and metrics["average_order_value"] < 60:
        lines.append(
            "The current basket size is modest, so bundling or shipping "
            "thresholds could lift revenue without new traffic."
        )

    return "\n".join(f"- {line}" for line in lines)


def customer_insights(metrics: Dict[str, Any]) -> str:
    if not metrics.get("unique_customers"):
        return "No customer rows are available in the active filter window."

    lines = [
        (
            f"{metrics['unique_customers']:,} unique buyers appear in the "
            f"active window; {_pct(metrics['repeat_ratio'])} have ordered "
            "more than once."
        ),
        (
            f"Average lifetime spend is "
            f"{_money(metrics['average_lifetime_spend'])} per customer."
        ),
    ]

    if metrics["repeat_ratio"] < 0.25:
        lines.append(
            "Retention is thin: most revenue depends on first-time buyers, so "
            "acquisition cost is carrying the growth model."
        )
    else:
        lines.append(
            "Repeat purchasing is a meaningful revenue base; protecting it is "
            "cheaper than buying equivalent new demand."
        )

    if metrics.get("top_state"):
        lines.append(
            f"Demand concentrates in {metrics['top_state']}, with "
            f"{metrics['city_count']} active cities in the current view."
        )

    return "\n".join(f"- {line}" for line in lines)


def product_insights(metrics: Dict[str, Any]) -> str:
    categories = metrics.get("top_categories") or []
    if not categories:
        return "No product rows are available in the active filter window."

    lines = []
    for entry in categories[:3]:
        lines.append(
            f"{entry['label'].replace('_', ' ').title()} generated "
            f"{_money(entry['value'])} ({_pct(entry['share'])} of category revenue)."
        )

    if categories[0]["share"] > 0.35:
        lines.append(
            "Revenue is concentrated in a single category, which raises "
            "assortment and supplier risk."
        )
    else:
        lines.append(
            "Revenue is reasonably diversified across categories, reducing "
            "single-category dependency."
        )

    if metrics.get("units_sold"):
        lines.append(
            f"Total units sold across the active catalog: "
            f"{metrics['units_sold']:,.0f}."
        )

    return "\n".join(f"- {line}" for line in lines)


def payment_insights(metrics: Dict[str, Any]) -> str:
    types = metrics.get("payment_types") or []
    if not types:
        return "No payment rows are available in the active filter window."

    leader = types[0]
    lines = [
        (
            f"{leader['label'].replace('_', ' ').title()} accounts for "
            f"{_pct(leader['share'])} of processed volume "
            f"({_money(leader['value'])})."
        )
    ]

    if leader["share"] > 0.5:
        lines.append(
            "Checkout is concentrated in one rail, so a failure or fee change "
            "there would hit most transactions."
        )
    else:
        lines.append(
            "Payment volume is spread across several rails, which limits "
            "single-rail risk."
        )

    if len(types) >= 2:
        runner_up = types[1]
        lines.append(
            f"{runner_up['label'].replace('_', ' ').title()} is the second "
            f"largest rail at {_pct(runner_up['share'])}."
        )

    return "\n".join(f"- {line}" for line in lines)


def review_insights(metrics: Dict[str, Any]) -> str:
    if not metrics.get("reviewed_orders"):
        return "No review scores are available in the active filter window."

    lines = [
        (
            f"Weighted satisfaction is {metrics['rating']:.2f}/5 across "
            f"{metrics['reviewed_orders']:,} reviewed orders."
        )
    ]

    negative = float(metrics["negative_review_share"])
    if negative >= 0.15:
        lines.append(
            f"{_pct(negative)} of reviews are at or below 2.5, a level that "
            "usually signals delivery or expectation failures worth a root-cause review."
        )
    elif negative >= 0.05:
        lines.append(
            f"{_pct(negative)} of reviews are at or below 2.5; this is within a "
            "normal band but worth monitoring by category."
        )
    else:
        lines.append(
            "Negative reviews are rare, indicating that fulfillment and product "
            "expectations are broadly being met."
        )

    return "\n".join(f"- {line}" for line in lines)


def recommendations(metrics: Dict[str, Any]) -> str:
    actions: List[str] = []

    if metrics.get("repeat_ratio", 0) < 0.30:
        actions.append(
            "Launch a post-purchase retention sequence with a second-order "
            "incentive to convert first-time buyers into repeat customers."
        )
    else:
        actions.append(
            "Protect the repeat base with a tiered loyalty offer and early "
            "access to new inventory."
        )

    if metrics.get("negative_review_share", 0) >= 0.10:
        actions.append(
            "Audit the lowest-rated categories and delivery promises, then "
            "close the top root causes before the next campaign push."
        )

    if metrics.get("top_categories"):
        leader = metrics["top_categories"][0]
        if leader["share"] > 0.35:
            actions.append(
                f"Reduce concentration risk by expanding adjacent assortment "
                f"around {leader['label'].replace('_', ' ')} and promoting a "
                "second category."
            )
        else:
            actions.append(
                f"Double down on {leader['label'].replace('_', ' ')} with "
                "bundled offers while the category mix is healthy."
            )

    if metrics.get("average_order_value", 0) < 60:
        actions.append(
            "Introduce bundles and free-shipping thresholds to raise average "
            "order value without increasing acquisition spend."
        )
    else:
        actions.append(
            "Use premium bundles and cross-sell placements to defend the "
            "current basket size."
        )

    if metrics.get("top_state"):
        actions.append(
            f"Concentrate localized marketing in {metrics['top_state']} first, "
            "then replicate the winning playbook in the next two states."
        )

    if metrics.get("payment_types"):
        leader = metrics["payment_types"][0]
        actions.append(
            f"Keep {leader['label'].replace('_', ' ')} checkout friction-free "
            "and monitor fees, since it carries most of the payment volume."
        )

    seen = set()
    unique_actions = []
    for action in actions:
        key = action.split(".")[0][:48]
        if key not in seen:
            seen.add(key)
            unique_actions.append(action)

    return "\n".join(
        f"{index}. {action}" for index, action in enumerate(unique_actions[:5], start=1)
    )


# --------------------------------------------------------------------------- #
# Chat copilot
# --------------------------------------------------------------------------- #


def _matches(question: str, keywords: Sequence[str]) -> bool:
    return any(keyword in question for keyword in keywords)


def answer_question(question: str, metrics: Dict[str, Any]) -> str:
    """Deterministic chat answer, routed by intent keywords."""

    lowered = (question or "").lower()

    if _matches(lowered, ("satisf", "review", "rating", "sentiment", "complain", "risk")):
        return (
            "**Satisfaction & review risk**\n\n"
            f"Scores average {metrics['rating']:.2f}/5 across "
            f"{metrics['reviewed_orders']:,} reviewed orders, with "
            f"{_pct(metrics['negative_review_share'])} at or below 2.5.\n\n"
            + review_insights(metrics)
        )

    if _matches(lowered, ("categor", "product", "sku", "item", "assortment")):
        return (
            "**Category performance**\n\n" + product_insights(metrics)
        )

    if _matches(lowered, ("payment", "checkout", "boleto", "credit", "pix")):
        return "**Payment mix**\n\n" + payment_insights(metrics)

    if _matches(lowered, ("state", "region", "geo", "market", "where", "location")):
        if not metrics.get("top_state"):
            return "No geographic data is available in the active filter window."
        breakdown = "\n".join(
            f"- {entry['label']}: {_money(entry['value'])}"
            for entry in _state_breakdown(metrics)
        )
        return (
            "**Where to focus next**\n\n"
            f"{metrics['top_state']} is the largest market at "
            f"{_pct(metrics['top_state_share'])} of order rows. "
            f"Start with {metrics['top_city'].title() if metrics['top_city'] else metrics['top_state']}, "
            "then expand to the next strongest states.\n\n" + breakdown
        )

    if _matches(lowered, ("customer", "loyal", "repeat", "retention", "segment")):
        return "**Customer base**\n\n" + customer_insights(metrics)

    if _matches(lowered, ("revenue", "sale", "sell", "growth", "trend", "order")):
        return "**Sales performance**\n\n" + sales_insights(metrics)

    if _matches(lowered, ("summary", "overview", "executive", "how are we", "health")):
        return "**Executive overview**\n\n" + executive_summary(metrics)

    return (
        "**Closest available analysis**\n\n"
        "I could not map that question to a specific domain, so here is the "
        "current executive snapshot.\n\n" + executive_summary(metrics)
    )


def _state_breakdown(metrics: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Return the pre-computed state breakdown, when the caller supplied one."""

    breakdown = metrics.get("state_breakdown")
    if isinstance(breakdown, list) and breakdown:
        return breakdown[:limit]
    return []
