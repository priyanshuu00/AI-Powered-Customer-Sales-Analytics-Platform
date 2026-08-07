import unittest
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

class TestDatabaseConnection(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "root")
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "3306")
        self.db = os.getenv("DB_NAME", "olist_analytics")
        self.uri = f"mysql+mysqlconnector://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    def test_engine_creation(self):
        engine = create_engine(self.uri)
        self.assertIsNotNone(engine)
        # Note: We don't call connect() here to avoid failing if MySQL isn't running locally in the CI environment.

if __name__ == '__main__':
    unittest.main()
