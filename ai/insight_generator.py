"""Business insight generation from dashboard summaries."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .gemini_client import GeminiClient
from .prompt_builder import PromptBuilder
from .ai_logger import setup_logger

logger = setup_logger("InsightGenerator")


class InsightGenerator:
    def __init__(self, client: GeminiClient):
        self.client = client

    def generate(self, domain: str, data: Any) -> str:
        logger.info("Generating insights for domain: %s", domain)

        if data is None:
            data = {}
        if isinstance(data, pd.DataFrame) and data.empty:
            return f"No {domain.lower()} data available for insight generation."

        prompt = PromptBuilder.build_insights_prompt(domain, data)
        response = self.client.generate_response(prompt)
        if response:
            return response

        logger.warning("Insight generation returned no content.")
        return self.client.unavailable_message("insights")
