"""
Database Module - Connection Handler
Manages SQLAlchemy engine creation and MySQL connection lifecycle.
"""

import os
from typing import Optional
from sqlalchemy import create_engine, Engine
from dotenv import load_dotenv

load_dotenv()

class DatabaseConnector:
    """Manages database connection pool and engine instantiation."""
    
    def __init__(self) -> None:
        self.host: str = os.getenv("DB_HOST", "localhost")
        self.port: int = int(os.getenv("DB_PORT", "3306"))
        self.user: str = os.getenv("DB_USER", "root")
        self.password: str = os.getenv("DB_PASSWORD", "")
        self.database: str = os.getenv("DB_NAME", "sales_analytics_db")
        self._engine: Optional[Engine] = None

    def get_connection_url(self) -> str:
        """Construct SQLAlchemy MySQL connection URL string."""
        return f"mysql+mysqlconnector://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    def get_engine(self) -> Engine:
        """Initialize and return SQLAlchemy Engine instance."""
        if not self._engine:
            connection_url = self.get_connection_url()
            self._engine = create_engine(connection_url, pool_recycle=3600)
        return self._engine
