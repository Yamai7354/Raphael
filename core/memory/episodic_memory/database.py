import re

from ai_router.database import DatabaseManager


class EpisodicDatabaseManager(DatabaseManager):
    """SQLite-backed compatibility layer for episodic memory storage."""

    @staticmethod
    def _normalize_query(query: str) -> str:
        # Convert PostgreSQL-style placeholders ($1, $2, ...) to sqlite3 placeholders (?).
        return re.sub(r"\$\d+", "?", query)

    @staticmethod
    def _normalize_parameters(*parameters):
        if len(parameters) == 1 and isinstance(parameters[0], tuple):
            return parameters[0]
        return tuple(parameters)

    async def execute_query(self, query: str, *parameters) -> None:
        await super().execute_query(
            self._normalize_query(query),
            self._normalize_parameters(*parameters),
        )

    async def fetch_one(self, query: str, *parameters):
        return await super().fetch_one(
            self._normalize_query(query),
            self._normalize_parameters(*parameters),
        )

    async def fetch_all(self, query: str, *parameters):
        return await super().fetch_all(
            self._normalize_query(query),
            self._normalize_parameters(*parameters),
        )


db_manager = EpisodicDatabaseManager()
