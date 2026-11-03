"""Plotly chart builders for the 2026 glassmorphic dashboard.

Every builder funnels through :func:`apply_2026_theme`, which owns the
transparent canvas, neon colorway, typography, grid, hover, and donut styling.
Legacy method names (``line_chart``, ``bar_chart``, ...) remain available for
backward compatibility.
"""

from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

NEON_COLORWAY: Sequence[str] = (
    "#6366F1",
    "#06B6D4",
    "#10B981",
    "#F59E0B",
    "#EC4899",
    "#8B5CF6",
    "#3B82F6",
)

TRANSPARENT = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(148, 163, 184, 0.08)"
AXIS_COLOR = "#94A3B8"
TITLE_COLOR = "#E2E8F0"
HOVERLABEL = dict(
    bgcolor="#0F172A",
    bordercolor="#334155",
    font=dict(color="#F8FAFC", size=13),
)


def _style_axes(fig: go.Figure) -> None:
    axis_style = dict(
        showgrid=True,
        gridcolor=GRID_COLOR,
        gridwidth=1,
        zeroline=False,
        showline=False,
        ticks="",
        tickfont=dict(color=AXIS_COLOR, size=11),
        title_font=dict(color="#64748B", size=11),
        automargin=True,
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)


def apply_2026_theme(fig: go.Figure, title: Optional[str] = None) -> go.Figure:
    """Apply the shared transparent/neon/glass theme to any Plotly figure."""

    fig.update_layout(
        template=None,
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        colorway=list(NEON_COLORWAY),
        font=dict(family="Inter, sans-serif", color=AXIS_COLOR, size=12),
        hoverlabel=HOVERLABEL,
        margin=dict(l=18, r=18, t=54 if title else 20, b=18),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=1,
            xanchor="right",
            bgcolor=TRANSPARENT,
            font=dict(color=AXIS_COLOR, size=11),
        ),
        hovermode="closest",
    )

    if title:
        fig.update_layout(
            title=dict(
                text=title,
                x=0.01,
                xanchor="left",
                y=0.97,
                yanchor="top",
                font=dict(
                    family="Inter, sans-serif",
                    size=15,
                    color=TITLE_COLOR,
                ),
            )
        )
    else:
        fig.update_layout(title_text="")

    _style_axes(fig)

    # Rounded bars are available in Plotly >= 5.19. Guard for older installs.
    try:
        fig.update_layout(barcornerradius=6)
    except Exception:
        pass

    return fig


def _round_bar_corners(fig: go.Figure) -> None:
    """Apply rounded bar corners with a guarded fallback."""

    try:
        fig.update_traces(marker_cornerradius=6, selector=dict(type="bar"))
        return
    except Exception:
        pass

    try:
        fig.update_traces(
            marker=dict(cornerradius=6),
            selector=dict(type="bar"),
        )
    except Exception:
        pass


def create_line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: Optional[str] = None,
) -> go.Figure:
    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        title=title,
        template=None,
        color_discrete_sequence=list(NEON_COLORWAY),
    )
    fig.update_traces(
        line=dict(shape="spline", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(99, 102, 241, 0.12)",
        mode="lines",
        hovertemplate="<b>%{x}</b><br>$%{y:,.2f}<extra></extra>",
    )
    apply_2026_theme(fig, title)
    fig.update_layout(hovermode="x unified")
    return fig


def create_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: Optional[str] = None,
    orientation: str = "v",
) -> go.Figure:
    fig = px.bar(
        df,
        x=x,
        y=y,
        color=color,
        title=title,
        template=None,
        orientation=orientation,
        color_discrete_sequence=list(NEON_COLORWAY),
    )
    fig.update_traces(marker_line_width=0)
    _round_bar_corners(fig)

    if orientation == "h":
        hovertemplate = "<b>%{y}</b><br>%{x:,.2f}<extra></extra>"
    else:
        hovertemplate = "<b>%{x}</b><br>%{y:,.2f}<extra></extra>"
    fig.update_traces(hovertemplate=hovertemplate)

    apply_2026_theme(fig, title)
    fig.update_layout(bargap=0.34)
    return fig


def create_pie_chart(
    df: pd.DataFrame,
    names: str,
    values: str,
    title: str = "",
) -> go.Figure:
    """Sleek donut chart with a centered total and adaptive legend."""

    fig = px.pie(
        df,
        names=names,
        values=values,
        hole=0.62,
        title=title,
        template=None,
        color_discrete_sequence=list(NEON_COLORWAY),
    )

    numeric_values = pd.to_numeric(df[values], errors="coerce").fillna(0)
    total = float(numeric_values.sum())

    fig.update_traces(
        textinfo="percent",
        textposition="inside",
        textfont=dict(color="#E2E8F0", size=11),
        marker=dict(line=dict(color="#0B1220", width=2)),
        hovertemplate=(
            "<b>%{label}</b><br>%{value:,.0f} · %{percent}<extra></extra>"
        ),
    )

    apply_2026_theme(fig, title)

    if len(df) <= 6:
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.14,
                x=0.5,
                xanchor="center",
                bgcolor=TRANSPARENT,
                font=dict(color=AXIS_COLOR, size=10),
            ),
            margin=dict(l=18, r=18, t=54 if title else 20, b=40),
        )
    else:
        fig.update_traces(showlegend=False)

    # Center label: total value with a JetBrains Mono numeric treatment.
    fig.add_annotation(
        text=(
            "<span style='font-size:10px;color:#94A3B8;"
            "letter-spacing:0.14em'>TOTAL</span><br>"
            "<span style='font-size:19px;color:#F8FAFC;"
            "font-family:JetBrains Mono, monospace'>"
            f"{total:,.0f}</span>"
        ),
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        align="center",
        font=dict(family="Inter, sans-serif"),
    )

    return fig


def create_scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    size: Optional[str] = None,
    color: Optional[str] = None,
) -> go.Figure:
    fig = px.scatter(
        df,
        x=x,
        y=y,
        size=size,
        color=color,
        title=title,
        template=None,
        color_discrete_sequence=list(NEON_COLORWAY),
    )

    marker: dict = dict(
        opacity=0.85,
        line=dict(width=1, color="rgba(248, 250, 252, 0.25)"),
    )
    if size is None:
        marker["size"] = 10

    fig.update_traces(
        marker=marker,
        hovertemplate="<b>%{x}</b><br>%{y:,.2f}<extra></extra>",
    )
    apply_2026_theme(fig, title)
    return fig


def create_treemap(
    df: pd.DataFrame,
    path: list,
    values: str,
    title: str = "",
) -> go.Figure:
    fig = px.treemap(
        df,
        path=path,
        values=values,
        title=title,
        template=None,
        color_discrete_sequence=list(NEON_COLORWAY),
    )
    fig.update_traces(
        marker=dict(line=dict(color="#0B1220", width=1)),
        textfont=dict(color="#F8FAFC"),
        hovertemplate="<b>%{label}</b><br>%{value:,.2f}<extra></extra>",
    )
    apply_2026_theme(fig, title)
    return fig


class ChartBuilder:
    """Backward-compatible facade over the module-level chart builders."""

    apply_2026_theme = staticmethod(apply_2026_theme)

    create_line_chart = staticmethod(create_line_chart)
    create_bar_chart = staticmethod(create_bar_chart)
    create_pie_chart = staticmethod(create_pie_chart)
    create_scatter_chart = staticmethod(create_scatter_chart)
    create_treemap = staticmethod(create_treemap)

    # Legacy names.
    line_chart = staticmethod(create_line_chart)
    bar_chart = staticmethod(create_bar_chart)
    pie_chart = staticmethod(create_pie_chart)
    scatter_chart = staticmethod(create_scatter_chart)
    treemap = staticmethod(create_treemap)
