"""Executive summary generation from KPI dictionaries or frames."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .gemini_client import GeminiClient
from .prompt_builder import PromptBuilder
from .ai_logger import setup_logger

logger = setup_logger("ExecutiveSummary")


class ExecutiveSummaryGenerator:
    def __init__(self, client: GeminiClient):
        self.client = client

    def generate(self, kpi_data: Any) -> str:
        logger.info("Generating executive summary...")

        if kpi_data is None:
            kpi_data = {}
        if isinstance(kpi_data, pd.DataFrame) and kpi_data.empty:
            return "No KPI data available for executive summary generation."

        prompt = PromptBuilder.build_executive_summary_prompt(kpi_data)
        response = self.client.generate_response(prompt)
        if response:
            return response

        logger.warning("Executive summary generation returned no content.")
        return self.client.unavailable_message("executive summary")
