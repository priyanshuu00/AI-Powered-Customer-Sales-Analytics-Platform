import os
import google.generativeai as genai
from dotenv import load_dotenv
from .ai_logger import setup_logger
from typing import Optional, Dict

logger = setup_logger("GeminiClient")

class GeminiClient:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found in environment variables.")
            raise ValueError("GEMINI_API_KEY is missing.")
            
        genai.configure(api_key=self.api_key)
        # Setup model - prefer the latest pro model for analytical tasks
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self.cache: Dict[str, str] = {}

    def generate_response(self, prompt: str, use_cache: bool = True) -> Optional[str]:
        if use_cache and prompt in self.cache:
            logger.info("Returning cached response for prompt.")
            return self.cache[prompt]
            
        logger.info("Sending request to Gemini API...")
        try:
            # Generate content handles its own HTTP timeouts generally, but wrapped in try-except for safety
            response = self.model.generate_content(prompt)
            if response and response.text:
                if use_cache:
                    self.cache[prompt] = response.text
                return response.text
            else:
                logger.warning("Received empty or invalid response from Gemini.")
                return None
        except Exception as e:
            logger.error(f"Failed to generate response from Gemini: {str(e)}")
            return None
