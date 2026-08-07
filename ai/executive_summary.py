from .gemini_client import GeminiClient
from .prompt_builder import PromptBuilder
from .ai_logger import setup_logger

logger = setup_logger("ExecutiveSummary")

class ExecutiveSummaryGenerator:
    def __init__(self, client: GeminiClient):
        self.client = client

    def generate(self, kpi_data: dict) -> str:
        logger.info("Generating executive summary...")
        prompt = PromptBuilder.build_executive_summary_prompt(kpi_data)
        response = self.client.generate_response(prompt)
        return response if response else "Failed to generate executive summary."
