"""Actionable recommendation generation from insight text or frames."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .gemini_client import GeminiClient
from .prompt_builder import PromptBuilder
from .ai_logger import setup_logger

logger = setup_logger("RecommendationEngine")


class RecommendationEngine:
    def __init__(self, client: GeminiClient):
        self.client = client

    def generate(self, insights: Any) -> str:
        logger.info("Generating business recommendations based on insights...")

        if insights is None:
            insights = ""
        if isinstance(insights, pd.DataFrame) and insights.empty:
            return "No insights available for recommendation generation."
        if isinstance(insights, str) and not insights.strip():
            return "No insights available for recommendation generation."

        prompt = PromptBuilder.build_recommendations_prompt(insights)
        response = self.client.generate_response(prompt)
        if response:
            return response

        logger.warning("Recommendation generation returned no content.")
        return self.client.unavailable_message("recommendations")
