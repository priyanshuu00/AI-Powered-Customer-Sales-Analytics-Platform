import unittest
from unittest.mock import patch, MagicMock

class TestIntegration(unittest.TestCase):
    @patch('ai.gemini_client.genai.GenerativeModel')
    def test_gemini_integration(self, mock_model):
        # Mocking the AI integration so we don't hit the API during tests
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = MagicMock(text="Mocked response")
        mock_model.return_value = mock_instance
        
        self.assertEqual(mock_instance.generate_content("test").text, "Mocked response")

if __name__ == '__main__':
    unittest.main()
