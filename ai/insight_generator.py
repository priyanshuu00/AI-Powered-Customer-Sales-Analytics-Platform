from .gemini_client import GeminiClient
from .prompt_builder import PromptBuilder
from .ai_logger import setup_logger

logger = setup_logger("InsightGenerator")

class InsightGenerator:
    def __init__(self, client: GeminiClient):
        self.client = client

    def generate(self, domain: str, data: dict) -> str:
        logger.info(f"Generating insights for domain: {domain}")
        prompt = PromptBuilder.build_insights_prompt(domain, data)
        response = self.client.generate_response(prompt)
        return response if response else "Failed to generate insights."
