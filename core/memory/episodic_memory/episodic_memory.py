import logging
import os

from .postgres_store import PostgresEpisodicStore

logger = logging.getLogger("raphael.memory.episodic_memory")

# Get DB URL from environment, defaulting to local postgres
DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgres@localhost:5432/raphael")

# Singleton
episodic_memory = PostgresEpisodicStore(db_url=DB_URL)
