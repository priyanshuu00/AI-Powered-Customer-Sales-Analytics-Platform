from .gemini_client import GeminiClient
from .prompt_builder import PromptBuilder
from .ai_logger import setup_logger

logger = setup_logger("RecommendationEngine")

class RecommendationEngine:
    def __init__(self, client: GeminiClient):
        self.client = client

    def generate(self, insights: str) -> str:
        logger.info("Generating business recommendations based on insights...")
        prompt = PromptBuilder.build_recommendations_prompt(insights)
        response = self.client.generate_response(prompt)
        return response if response else "Failed to generate recommendations."
