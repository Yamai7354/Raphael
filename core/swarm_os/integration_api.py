"""
SOS-514 — Integration API for External Systems.

Standard query and command interfaces for external tools,
APIs, and datasets. Secure communication, tool/source discovery.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("core.swarm_os.integration_api")


@dataclass
class ExternalConnection:
    """A registered external system connection."""

    conn_id: str = field(default_factory=lambda: f"ext_{uuid.uuid4().hex[:8]}")
    name: str = ""
    endpoint: str = ""
    conn_type: str = "api"  # api, database, tool, dataset
    auth_method: str = "none"  # none, api_key, oauth, token
    status: str = "active"
    call_count: int = 0
    error_count: int = 0
    registered_at: float = field(default_factory=time.time)

    @property
    def reliability(self) -> float:
        if self.call_count == 0:
            return 1.0
        return (self.call_count - self.error_count) / self.call_count

    def to_dict(self) -> dict:
        return {
            "conn_id": self.conn_id,
            "name": self.name,
            "type": self.conn_type,
            "status": self.status,
            "reliability": round(self.reliability, 3),
            "calls": self.call_count,
        }


class IntegrationAPI:
    """Manages external system integrations."""

    def __init__(self):
        self._connections: dict[str, ExternalConnection] = {}
        self._by_name: dict[str, str] = {}
        self._query_log: list[dict] = []

    def register(
        self, name: str, endpoint: str = "", conn_type: str = "api", auth_method: str = "none"
    ) -> ExternalConnection:
        if name in self._by_name:
            return self._connections[self._by_name[name]]

        conn = ExternalConnection(
            name=name,
            endpoint=endpoint,
            conn_type=conn_type,
            auth_method=auth_method,
        )
        self._connections[conn.conn_id] = conn
        self._by_name[name] = conn.conn_id
        logger.info("external_registered name=%s type=%s", name, conn_type)
        return conn

    def query(self, connection_name: str, query_data: dict) -> dict:
        """Execute a query against an external system (simulated)."""
        cid = self._by_name.get(connection_name)
        if not cid or cid not in self._connections:
            return {"error": f"Unknown connection: {connection_name}"}

        conn = self._connections[cid]
        if conn.status != "active":
            return {"error": f"Connection {connection_name} is {conn.status}"}

        conn.call_count += 1
        self._query_log.append(
            {
                "connection": connection_name,
                "query": query_data,
                "timestamp": time.time(),
            }
        )
        return {"status": "ok", "connection": connection_name, "query": query_data}

    def record_error(self, connection_name: str) -> None:
        cid = self._by_name.get(connection_name)
        if cid and cid in self._connections:
            self._connections[cid].error_count += 1

    def discover(self, capability: str = "") -> list[ExternalConnection]:
        """Discover available external connections."""
        if not capability:
            return [c for c in self._connections.values() if c.status == "active"]
        cap = capability.lower()
        return [
            c for c in self._connections.values() if c.status == "active" and cap in c.name.lower()
        ]

    def set_status(self, connection_name: str, status: str) -> None:
        cid = self._by_name.get(connection_name)
        if cid and cid in self._connections:
            self._connections[cid].status = status

    def get_all(self) -> list[dict]:
        return [c.to_dict() for c in self._connections.values()]

    def get_query_log(self, limit: int = 20) -> list[dict]:
        return self._query_log[-limit:]

    def get_stats(self) -> dict:
        active = sum(1 for c in self._connections.values() if c.status == "active")
        return {
            "total_connections": len(self._connections),
            "active": active,
            "total_queries": sum(c.call_count for c in self._connections.values()),
            "total_errors": sum(c.error_count for c in self._connections.values()),
        }
