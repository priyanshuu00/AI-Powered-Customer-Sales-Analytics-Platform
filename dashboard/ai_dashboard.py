"""AI Insights & Copilot tab plus the deterministic analyst fallback.

The tab wires the ``ai`` package into the dashboard. Every generation path is
wrapped: if Gemini is not configured, rate-limited, offline, or returns an
unusable response, the same question is answered from the *actual* filtered
DataFrames by :mod:`dashboard.local_analyst`, so the UI never shows raw errors.
"""

from __future__ import annotations

import html
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd
import streamlit as st

from ai.executive_summary import ExecutiveSummaryGenerator
from ai.gemini_client import GeminiClient
from ai.insight_generator import InsightGenerator
from ai.recommendation_engine import RecommendationEngine
from ai.report_generator import AIReportGenerator, ChatInterface

from dashboard import local_analyst
from dashboard.database import get_data_source_status, get_source_label
from dashboard.theme import render_section_header

_CLIENT_KEY = "_ai_client"
_RESULTS_KEY = "ai_results"
_CHAT_KEY = "ai_chat_history"
_DEGRADED_KEY = "_ai_runtime_degraded"
_DOWN_UNTIL_KEY = "_ai_down_until"
_DOWN_COOLDOWN_SECONDS = 180
_REPORT_FILENAME = "executive_ai_report.md"

QUICK_PROMPTS = (
    "Which product categories drive the highest revenue?",
    "Summarize customer satisfaction & review risks",
    "Where should we focus marketing by state?",
)

_KPI_KEYS = (
    "revenue",
    "orders",
    "average_order_value",
    "unique_customers",
    "repeat_ratio",
    "average_lifetime_spend",
    "rating",
    "negative_review_share",
    "reviewed_orders",
    "top_state",
    "top_state_share",
    "top_city",
    "state_count",
    "city_count",
    "units_sold",
    "payment_volume",
    "momentum",
)

_DOMAIN_FRAMES: Dict[str, Tuple[str, Callable[[Dict[str, Any]], str]]] = {
    "Sales": ("sales", local_analyst.sales_insights),
    "Customers": ("customers", local_analyst.customer_insights),
    "Products": ("products", local_analyst.product_insights),
    "Payments": ("payments", local_analyst.payment_insights),
    "Reviews": ("reviews", local_analyst.review_insights),
}

_SECTION_MAP = {
    "Sales": "sales_insights",
    "Customers": "customer_insights",
    "Products": "product_insights",
    "Payments": "payment_insights",
    "Reviews": "review_insights",
}


# --------------------------------------------------------------------------- #
# Client + state helpers
# --------------------------------------------------------------------------- #


def _get_client() -> GeminiClient:
    client = st.session_state.get(_CLIENT_KEY)
    if not isinstance(client, GeminiClient):
        client = GeminiClient()
        st.session_state[_CLIENT_KEY] = client
    return client


def _is_ai_failure(text: Optional[str]) -> bool:
    """True when a generator returned a placeholder instead of real content."""

    if text is None:
        return True
    value = str(text).strip()
    if not value:
        return True

    lowered = value.lower()
    if lowered.startswith("ai ") and "unavailable:" in lowered:
        return True
    if lowered.startswith("i'm sorry, i could not process that request"):
        return True
    if lowered.startswith("no ") and "data available" in lowered:
        return True
    if "gemini returned" in lowered and "no content" in lowered:
        return True
    return False


def _ai_available() -> bool:
    """Circuit breaker so a dead API is not retried on every widget click."""

    down_until = st.session_state.get(_DOWN_UNTIL_KEY)
    try:
        return time.time() >= float(down_until or 0.0)
    except (TypeError, ValueError):
        return True


def _mark_ai_unavailable() -> None:
    st.session_state[_DOWN_UNTIL_KEY] = time.time() + _DOWN_COOLDOWN_SECONDS
    st.session_state[_DEGRADED_KEY] = True


def _store_result(key: str, text: str, source: str, model: str) -> None:
    results = st.session_state.get(_RESULTS_KEY)
    if not isinstance(results, dict):
        results = {}
    results[key] = {
        "text": text,
        "source": source,
        "model": model,
        "generated_at": datetime.now().strftime("%H:%M"),
    }
    st.session_state[_RESULTS_KEY] = results
    st.session_state[_DEGRADED_KEY] = source == "fallback"


def _results() -> Dict[str, Dict[str, Any]]:
    results = st.session_state.get(_RESULTS_KEY)
    return results if isinstance(results, dict) else {}


def _source_label(source: str) -> str:
    return "Gemini" if source == "gemini" else "Deterministic"


# --------------------------------------------------------------------------- #
# Context snapshot
# --------------------------------------------------------------------------- #


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _active_filters() -> Dict[str, Any]:
    date_range = st.session_state.get("date_range_filter")
    states = st.session_state.get("state_filter") or []

    formatted_range = None
    if date_range is not None:
        try:
            values = list(date_range)
            if len(values) == 2:
                formatted_range = [
                    str(pd.to_datetime(values[0]).date()),
                    str(pd.to_datetime(values[1]).date()),
                ]
        except (TypeError, ValueError):
            formatted_range = None

    return {
        "date_range": formatted_range,
        "states": [str(state) for state in states][:10],
    }


def _build_context(
    frames: Dict[str, pd.DataFrame], metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Compact snapshot passed to Gemini chat and insight prompts."""

    source = get_data_source_status()
    return {
        "data_source": source.get("mode", "unknown"),
        "active_filters": _active_filters(),
        "kpis": {key: metrics.get(key) for key in _KPI_KEYS},
        "sales": {
            "row_count": metrics["rows"]["sales"],
            "monthly_revenue": metrics.get("monthly_revenue", [])[-6:],
            "top_states": metrics.get("state_breakdown", [])[:5],
        },
        "customers": {
            "row_count": metrics["rows"]["customers"],
            "repeat_ratio": metrics.get("repeat_ratio"),
            "top_state": metrics.get("top_state"),
        },
        "products": {
            "row_count": metrics["rows"]["products"],
            "top_categories": metrics.get("top_categories", [])[:5],
        },
        "payments": {
            "row_count": metrics["rows"]["payments"],
            "top_types": metrics.get("payment_types", [])[:5],
        },
        "reviews": {
            "row_count": metrics["rows"]["reviews"],
            "average_rating": metrics.get("rating"),
            "negative_share": metrics.get("negative_review_share"),
        },
    }


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #


def _generate_executive(
    client: GeminiClient, metrics: Dict[str, Any]
) -> Tuple[str, str]:
    fallback_text = local_analyst.executive_summary(metrics)
    if not _ai_available():
        return fallback_text, "fallback"

    try:
        text = ExecutiveSummaryGenerator(client).generate(
            {key: metrics.get(key) for key in _KPI_KEYS}
        )
    except Exception:
        text = None

    if _is_ai_failure(text):
        if client.is_configured:
            _mark_ai_unavailable()
        return fallback_text, "fallback"
    return str(text).strip(), "gemini"


def _generate_domains(
    client: GeminiClient,
    frames: Dict[str, pd.DataFrame],
    metrics: Dict[str, Any],
    domains: Tuple[str, ...] = ("Sales", "Customers", "Products"),
) -> Dict[str, Dict[str, str]]:
    generator = InsightGenerator(client)
    output: Dict[str, Dict[str, str]] = {}

    for domain in domains:
        frame_key, fallback = _DOMAIN_FRAMES[domain]

        if not _ai_available():
            output[domain] = {"text": fallback(metrics), "source": "fallback"}
            continue

        try:
            text = generator.generate(domain, frames[frame_key])
        except Exception:
            text = None

        if _is_ai_failure(text):
            if client.is_configured:
                _mark_ai_unavailable()
            output[domain] = {"text": fallback(metrics), "source": "fallback"}
        else:
            output[domain] = {"text": str(text).strip(), "source": "gemini"}

    return output


def _combine_domain_insights(domain_output: Dict[str, Dict[str, str]]) -> str:
    return "\n\n".join(
        f"**{domain}**\n\n{entry['text']}" for domain, entry in domain_output.items()
    )


def _generate_recommendations(
    client: GeminiClient,
    insight_text: str,
    metrics: Dict[str, Any],
) -> Tuple[str, str]:
    fallback_text = local_analyst.recommendations(metrics)
    if not _ai_available():
        return fallback_text, "fallback"

    try:
        text = RecommendationEngine(client).generate(insight_text)
    except Exception:
        text = None

    if _is_ai_failure(text):
        if client.is_configured:
            _mark_ai_unavailable()
        return fallback_text, "fallback"
    return str(text).strip(), "gemini"


def _run_executive(client: GeminiClient, frames, metrics) -> None:
    text, source = _generate_executive(client, metrics)
    _store_result("executive", text, source, client.model_name)


def _run_insights(client: GeminiClient, frames, metrics) -> None:
    generated = _generate_domains(client, frames, metrics)
    sources = {entry["source"] for entry in generated.values()}
    source = "gemini" if sources == {"gemini"} else "fallback"
    _store_result(
        "insights",
        _combine_domain_insights(generated),
        source,
        client.model_name,
    )


def _run_recommendations(client: GeminiClient, frames, metrics) -> None:
    generated = _generate_domains(client, frames, metrics)
    text, source = _generate_recommendations(
        client, _combine_domain_insights(generated), metrics
    )
    _store_result("recommendations", text, source, client.model_name)


def _run_full_report(client: GeminiClient, frames, metrics) -> None:
    domains = tuple(_DOMAIN_FRAMES)
    generated = _generate_domains(client, frames, metrics, domains=domains)

    executive_text, executive_source = _generate_executive(client, metrics)
    recommendations_text, recommendations_source = _generate_recommendations(
        client, _combine_domain_insights(generated), metrics
    )

    sections = {
        "executive_summary": executive_text,
        "recommendations": recommendations_text,
    }
    for domain, section_key in _SECTION_MAP.items():
        sections[section_key] = generated[domain]["text"]

    mode = get_data_source_status().get("mode", "unknown")
    source = (
        "gemini"
        if executive_source == "gemini"
        and recommendations_source == "gemini"
        and all(entry["source"] == "gemini" for entry in generated.values())
        else "fallback"
    )

    meta = {
        "data_source": f"{mode} dashboard views",
        "engine": "Gemini + deterministic guardrails"
        if source == "gemini"
        else "Deterministic analyst fallback",
    }

    generator = AIReportGenerator(client)
    try:
        report = generator.generate_full_report(
            {key: metrics.get(key) for key in _KPI_KEYS},
            frames["sales"],
            frames["customers"],
            product_data=frames["products"],
            payment_data=frames["payments"],
            review_data=frames["reviews"],
            sections=sections,
            filename=_REPORT_FILENAME,
            save=True,
            meta=meta,
        )
    except Exception:
        # Never let report persistence take down the tab.
        report = AIReportGenerator.render_report(sections, meta=meta)
        st.session_state["ai_report_path"] = ""

    # Mirror the individual cards so every section is visible after the run.
    core_domains = {
        domain: generated[domain] for domain in ("Sales", "Customers", "Products")
    }
    core_source = (
        "gemini"
        if all(entry["source"] == "gemini" for entry in core_domains.values())
        else "fallback"
    )
    _store_result("executive", executive_text, executive_source, client.model_name)
    _store_result(
        "insights",
        _combine_domain_insights(core_domains),
        core_source,
        client.model_name,
    )
    _store_result(
        "recommendations",
        recommendations_text,
        recommendations_source,
        client.model_name,
    )
    _store_result("report", report, source, client.model_name)
    st.session_state["ai_report_path"] = str(generator.last_report_path or "")


def _answer_question(
    client: GeminiClient,
    question: str,
    frames: Dict[str, pd.DataFrame],
    metrics: Dict[str, Any],
) -> None:
    history = st.session_state.get(_CHAT_KEY)
    if not isinstance(history, list):
        history = []

    history.append({"role": "user", "content": question, "source": "user"})

    if _ai_available():
        context = _build_context(frames, metrics)
        chat = ChatInterface(client, context)
        try:
            answer = chat.answer(question)
        except Exception:
            answer = None
    else:
        answer = None

    if _is_ai_failure(answer):
        if client.is_configured and _ai_available():
            _mark_ai_unavailable()
        text = local_analyst.answer_question(question, metrics)
        source = "fallback"
    else:
        text = str(answer).strip()
        source = "gemini"

    history.append({"role": "assistant", "content": text, "source": source})
    st.session_state[_CHAT_KEY] = history
    st.session_state[_DEGRADED_KEY] = source == "fallback"


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #


def _render_readiness_banner(client: GeminiClient) -> None:
    configured = bool(client.is_ready)
    degraded = bool(st.session_state.get(_DEGRADED_KEY))
    cooling_down = not _ai_available()
    data_mode = get_data_source_status().get("mode", "unknown")

    if configured and not degraded and not cooling_down:
        state = "live"
        pill_class = "live"
        pill = "Gemini Online"
        title = f"Gemini Copilot Online · {client.model_name}"
        copy = (
            "Live model access is available over HTTPS REST, so generation no "
            "longer depends on the gRPC channel that caused 504 timeouts. The "
            "deterministic analyst stays on standby as a guardrail."
        )
    elif client.is_configured:
        state = "degraded"
        pill_class = "demo"
        pill = "Fallback Active"
        title = "Smart Deterministic Analyst · Gemini temporarily unavailable"
        copy = (
            "The API key is configured but the last call failed (invalid key, "
            "quota, high demand, or network). Answers are derived from the "
            "filtered DataFrames while the circuit breaker cools down; Gemini is "
            "retried automatically after a few minutes."
        )
    else:
        state = "fallback"
        pill_class = "demo"
        pill = "Deterministic Mode"
        title = "Smart Deterministic Analyst · No Gemini key detected"
        copy = (
            "Add GEMINI_API_KEY to .env to enable live LLM narratives. Until "
            "then, every summary, insight, recommendation, and copilot answer "
            "is computed statistically from the active dashboard data."
        )

    data_label = get_source_label(data_mode)

    st.markdown(
        f'<div class="ai-banner ai-banner-{state}">'
        f'<div class="ai-banner-copy">'
        f'<div class="ai-banner-eyebrow">AI Copilot Readiness</div>'
        f'<div class="ai-banner-title">{html.escape(title)}</div>'
        f'<div class="ai-banner-text">{html.escape(copy)}</div>'
        f"</div>"
        f'<div class="ai-banner-side">'
        f'<span class="status-pill {pill_class}"><span class="dot"></span>'
        f"{html.escape(pill)}</span>"
        f'<span class="filter-pill">Data · {html.escape(data_label)}</span>'
        f'<span class="filter-pill">Model · {html.escape(client.model_name)}</span>'
        f'<span class="filter-pill">Transport · {html.escape(client.transport)}</span>'
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_result_card(key: str, title: str, entry: Dict[str, Any]) -> None:
    source = entry.get("source", "fallback")
    badge_class = "gemini" if source == "gemini" else "fallback"
    generated_at = entry.get("generated_at", "")

    with st.container(border=True, key=f"ai_result_{key}"):
        st.markdown(
            f'<div class="ai-result-head">'
            f'<div class="ai-result-title">{html.escape(title)}</div>'
            f'<div class="ai-result-meta">'
            f'<span class="ai-source-badge {badge_class}">'
            f"{_source_label(source)}</span>"
            f'<span class="ai-result-time">{html.escape(generated_at)}</span>'
            f"</div></div>",
            unsafe_allow_html=True,
        )

        if key == "report":
            st.download_button(
                "⬇ Download executive_ai_report.md",
                data=entry.get("text", ""),
                file_name=_REPORT_FILENAME,
                mime="text/markdown",
                key="ai_report_download",
            )
            with st.expander("Preview compiled report"):
                st.markdown(entry.get("text", ""))
            return

        st.markdown(entry.get("text", ""))


def _render_results() -> None:
    results = _results()
    order = (
        ("executive", "Executive Summary"),
        ("insights", "Automated Insights"),
        ("recommendations", "Strategic Recommendations"),
        ("report", "Compiled Executive Report"),
    )

    rendered = False
    for key, title in order:
        entry = results.get(key)
        if isinstance(entry, dict) and entry.get("text"):
            _render_result_card(key, title, entry)
            rendered = True

    if not rendered:
        st.caption(
            "No intelligence generated yet. Use the one-click suite above to "
            "build summaries, insights, recommendations, or the full report."
        )


def _render_chat(client: GeminiClient, frames, metrics) -> None:
    render_section_header(
        "Ask Data Copilot",
        "Natural-language questions answered from the filtered datasets.",
    )

    history = st.session_state.get(_CHAT_KEY)
    if not isinstance(history, list):
        history = []

    chip_columns = st.columns(len(QUICK_PROMPTS))
    for index, (column, prompt) in enumerate(zip(chip_columns, QUICK_PROMPTS)):
        with column:
            if st.button(
                prompt,
                key=f"ai_quick_{index}",
                width="stretch",
            ):
                _answer_question(client, prompt, frames, metrics)
                st.rerun()

    for message in st.session_state.get(_CHAT_KEY, []):
        role = message.get("role", "assistant")
        with st.chat_message(role):
            st.markdown(message.get("content", ""))
            if role == "assistant" and message.get("source") == "fallback":
                st.caption("Deterministic analyst fallback · computed from current data")

    chat_columns = st.columns([5, 1])
    with chat_columns[1]:
        if st.button("Clear chat", key="ai_chat_clear", width="stretch"):
            st.session_state[_CHAT_KEY] = []
            st.rerun()

    with st.form("ai_chat_form", clear_on_submit=True):
        question = st.text_input(
            "Ask the Data Copilot",
            placeholder="e.g. Where should we focus marketing by state?",
            label_visibility="collapsed",
            key="ai_chat_question",
        )
        submitted = st.form_submit_button("Send to Copilot", type="primary")

    if submitted and question and question.strip():
        _answer_question(client, question.strip(), frames, metrics)
        st.rerun()


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def render_ai_dashboard(
    sales_df: Optional[pd.DataFrame],
    customer_df: Optional[pd.DataFrame],
    product_df: Optional[pd.DataFrame],
    payment_df: Optional[pd.DataFrame],
    review_df: Optional[pd.DataFrame],
) -> None:
    frames = {
        "sales": sales_df if isinstance(sales_df, pd.DataFrame) else pd.DataFrame(),
        "customers": customer_df
        if isinstance(customer_df, pd.DataFrame)
        else pd.DataFrame(),
        "products": product_df if isinstance(product_df, pd.DataFrame) else pd.DataFrame(),
        "payments": payment_df if isinstance(payment_df, pd.DataFrame) else pd.DataFrame(),
        "reviews": review_df if isinstance(review_df, pd.DataFrame) else pd.DataFrame(),
    }

    metrics = local_analyst.compute_metrics(
        frames["sales"],
        frames["customers"],
        frames["products"],
        frames["payments"],
        frames["reviews"],
    )

    client = _get_client()

    render_section_header(
        "AI Insights & Copilot",
        "Executive narratives and a data-grounded chat assistant, with a "
        "deterministic fallback that never shows raw API errors.",
    )

    _render_readiness_banner(client)

    action_columns = st.columns(3)
    with action_columns[0]:
        if st.button(
            "Generate Executive Summary",
            key="ai_exec_button",
            type="primary",
            width="stretch",
        ):
            _run_executive(client, frames, metrics)
            st.rerun()
    with action_columns[1]:
        if st.button(
            "Analyze Automated Insights",
            key="ai_insights_button",
            width="stretch",
        ):
            _run_insights(client, frames, metrics)
            st.rerun()
    with action_columns[2]:
        if st.button(
            "Generate Strategic Recommendations",
            key="ai_reco_button",
            width="stretch",
        ):
            _run_recommendations(client, frames, metrics)
            st.rerun()

    if st.button(
        "Generate Full Executive Report",
        key="ai_report_button",
        type="primary",
        width="stretch",
    ):
        _run_full_report(client, frames, metrics)
        st.rerun()

    render_section_header(
        "Generated Intelligence",
        "Results persist across interactions and can be exported as Markdown.",
    )
    _render_results()

    _render_chat(client, frames, metrics)
