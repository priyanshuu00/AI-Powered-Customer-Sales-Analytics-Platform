"""Prompt construction with safe serialisation of dicts and DataFrames."""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any

import pandas as pd

MAX_ROWS = 60
MAX_CHARS = 12_000
MAX_DEPTH = 5


class PromptBuilder:
    @staticmethod
    def _clean(value: Any, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            return str(value)

        if isinstance(value, pd.DataFrame):
            return PromptBuilder._clean(
                value.head(MAX_ROWS).to_dict(orient="records"), depth + 1
            )

        if isinstance(value, pd.Series):
            return PromptBuilder._clean(
                value.head(MAX_ROWS).to_dict(), depth + 1
            )

        if isinstance(value, dict):
            return {
                str(key): PromptBuilder._clean(item, depth + 1)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            cleaned = [
                PromptBuilder._clean(item, depth + 1)
                for item in list(value)[:MAX_ROWS]
            ]
            return cleaned

        if isinstance(value, (datetime, date, pd.Timestamp)):
            return value.isoformat()

        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None

        if hasattr(value, "item"):
            try:
                return value.item()
            except (ValueError, AttributeError):
                pass

        if isinstance(value, (str, int, float, bool)) or value is None:
            return value

        return str(value)

    @staticmethod
    def _serialise(payload: Any) -> str:
        """Convert summary dicts/frames into a bounded JSON prompt payload."""

        cleaned = PromptBuilder._clean(payload)
        try:
            text = json.dumps(cleaned, indent=2, default=str)
        except (TypeError, ValueError):
            text = str(cleaned)
        return text[:MAX_CHARS]

    @staticmethod
    def build_executive_summary_prompt(metrics: Any) -> str:
        return f"""
        Act as a Senior Business Analyst. Based on the following e-commerce KPIs, generate an executive summary.
        Data:
        {PromptBuilder._serialise(metrics)}
        Include:
        - Overall business performance
        - Major achievements
        - Major risks
        - Business health score (out of 100)
        """

    @staticmethod
    def build_insights_prompt(domain: str, data: Any) -> str:
        return f"""
        Act as a Senior Data Scientist. Analyze the following {domain} data and extract 3-5 specific business insights.
        Data:
        {PromptBuilder._serialise(data)}
        Format as bullet points. Examples: "Revenue dropped 12%", "Average delivery time improved".
        Also include a Root Cause Analysis section identifying possible reasons for any negative trends (e.g., "Sales decreased because of high delivery delay").
        """

    @staticmethod
    def build_recommendations_prompt(insights: Any) -> str:
        return f"""
        Act as a Chief Strategy Officer. Based on the following business insights, generate 3-5 actionable business recommendations.
        Insights:
        {PromptBuilder._serialise(insights)}
        Format as bullet points. Examples: "Increase inventory", "Launch loyalty campaign".
        """

    @staticmethod
    def build_chat_prompt(question: str, context: Any) -> str:
        return f"""
        Act as an AI Business Intelligence Assistant. Answer the user's question clearly and concisely using the provided context.
        Context:
        {PromptBuilder._serialise(context)}
        User Question: {question}
        """
