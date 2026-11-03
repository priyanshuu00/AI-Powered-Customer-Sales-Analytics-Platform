"""Theme loader and shared layout helpers.

All visual styling lives in ``assets/style.css``; this module only injects it
and provides small HTML helpers used by the dashboard modules.
"""

from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

STYLESHEET_PATH = Path(__file__).resolve().parent.parent / "assets" / "style.css"

_FALLBACK_CSS = """
.stApp { background-color: #090D16; color: #F8FAFC; }
"""


def load_stylesheet() -> str:
    """Read the single-source stylesheet, falling back to a minimal theme."""

    try:
        css = STYLESHEET_PATH.read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_CSS
    return css if css.strip() else _FALLBACK_CSS


def apply_theme() -> None:
    """Inject ``assets/style.css`` into the Streamlit app."""

    st.markdown(f"<style>{load_stylesheet()}</style>", unsafe_allow_html=True)


def render_section_header(title: str, subtitle: str = "") -> None:
    """Render a compact executive section header above a chart row."""

    subtitle_html = (
        f'<div class="section-subtitle">{html.escape(subtitle)}</div>'
        if subtitle
        else ""
    )
    st.markdown(
        f'<div class="section-head">'
        f'<div class="section-title">{html.escape(title)}</div>'
        f"{subtitle_html}</div>",
        unsafe_allow_html=True,
    )


def render_divider() -> None:
    """Render the gradient divider used between layout sections."""

    st.markdown('<div class="bento-divider"></div>', unsafe_allow_html=True)
