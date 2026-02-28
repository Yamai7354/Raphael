"""
Alerting Mechanism for AI Router.

Monitors key metrics and triggers alerts when thresholds exceeded.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

logger = logging.getLogger("ai_router.alerting")


# =============================================================================
# ALERT TYPES
# =============================================================================


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts."""

    NODE_FAILURE = "node_failure"
    NODE_CIRCUIT_OPEN = "node_circuit_open"
    QUEUE_BACKLOG = "queue_backlog"
    HIGH_LATENCY = "high_latency"
    LOW_SUCCESS_RATE = "low_success_rate"
    VRAM_EXHAUSTION = "vram_exhaustion"
    TASK_FAILED = "task_failed"


# =============================================================================
# ALERT
# =============================================================================


@dataclass
class Alert:
    """A single alert instance."""

    alert_type: AlertType
    severity: AlertSeverity
    message: str
    triggered_at: datetime = field(default_factory=datetime.now)

    # Context
    node_id: Optional[str] = None
    task_id: Optional[str] = None
    role: Optional[str] = None

    # Metric values
    threshold: Optional[float] = None
    actual_value: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "triggered_at": self.triggered_at.isoformat(),
            "node_id": self.node_id,
            "task_id": self.task_id,
            "role": self.role,
            "threshold": self.threshold,
            "actual_value": self.actual_value,
        }


# =============================================================================
# ALERT RULES
# =============================================================================


@dataclass
class AlertRule:
    """Defines when to trigger an alert."""

    name: str
    alert_type: AlertType
    severity: AlertSeverity
    threshold: float
    message_template: str
    enabled: bool = True

    def check(self, value: float) -> bool:
        """Check if threshold exceeded."""
        return value >= self.threshold


# Default alert rules
DEFAULT_RULES = [
    AlertRule(
        name="queue_backlog_warning",
        alert_type=AlertType.QUEUE_BACKLOG,
        severity=AlertSeverity.WARNING,
        threshold=10,
        message_template="Queue backlog high: {value} steps waiting for role {role}",
    ),
    AlertRule(
        name="queue_backlog_critical",
        alert_type=AlertType.QUEUE_BACKLOG,
        severity=AlertSeverity.CRITICAL,
        threshold=50,
        message_template="Queue backlog critical: {value} steps waiting for role {role}",
    ),
    AlertRule(
        name="high_latency_warning",
        alert_type=AlertType.HIGH_LATENCY,
        severity=AlertSeverity.WARNING,
        threshold=5000,  # 5 seconds
        message_template="High latency on node {node_id}: {value}ms (threshold: {threshold}ms)",
    ),
    AlertRule(
        name="high_latency_critical",
        alert_type=AlertType.HIGH_LATENCY,
        severity=AlertSeverity.CRITICAL,
        threshold=30000,  # 30 seconds
        message_template="Critical latency on node {node_id}: {value}ms",
    ),
    AlertRule(
        name="low_success_rate",
        alert_type=AlertType.LOW_SUCCESS_RATE,
        severity=AlertSeverity.WARNING,
        threshold=20,  # 20% failure rate
        message_template="Low success rate on node {node_id}: {value}%",
    ),
    AlertRule(
        name="vram_exhaustion",
        alert_type=AlertType.VRAM_EXHAUSTION,
        severity=AlertSeverity.CRITICAL,
        threshold=95,  # 95% VRAM usage
        message_template="VRAM nearly exhausted on node {node_id}: {value}%",
    ),
]


# =============================================================================
# ALERTING SYSTEM
# =============================================================================


class AlertingSystem:
    """
    Central alerting system.
    """

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._rules: Dict[str, AlertRule] = {r.name: r for r in DEFAULT_RULES}
        self._alerts: List[Alert] = []
        self._handlers: List[Callable[[Alert], None]] = []

    def add_rule(self, rule: AlertRule) -> None:
        """Add or update an alert rule."""
        self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """Add alert handler (e.g., webhook, email)."""
        self._handlers.append(handler)

    def trigger(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        node_id: Optional[str] = None,
        task_id: Optional[str] = None,
        role: Optional[str] = None,
        threshold: Optional[float] = None,
        actual_value: Optional[float] = None,
    ) -> Alert:
        """Trigger an alert."""
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            node_id=node_id,
            task_id=task_id,
            role=role,
            threshold=threshold,
            actual_value=actual_value,
        )

        # Store alert
        self._alerts.append(alert)
        if len(self._alerts) > self.max_history:
            self._alerts = self._alerts[-self.max_history :]

        # Log alert
        log_level = (
            logging.WARNING if severity == AlertSeverity.WARNING else logging.ERROR
        )
        logger.log(
            log_level,
            "alert_triggered type=%s severity=%s node=%s task=%s msg=%s",
            alert_type.value,
            severity.value,
            node_id,
            task_id,
            message,
        )

        # Call handlers
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error("alert_handler_failed error=%s", str(e))

        return alert

    def check_queue_backlog(self, role: str, queue_size: int) -> Optional[Alert]:
        """Check queue backlog against rules."""
        for rule in self._rules.values():
            if rule.alert_type == AlertType.QUEUE_BACKLOG and rule.enabled:
                if rule.check(queue_size):
                    return self.trigger(
                        alert_type=AlertType.QUEUE_BACKLOG,
                        severity=rule.severity,
                        message=rule.message_template.format(
                            value=queue_size, role=role, threshold=rule.threshold
                        ),
                        role=role,
                        threshold=rule.threshold,
                        actual_value=queue_size,
                    )
        return None

    def check_latency(self, node_id: str, latency_ms: float) -> Optional[Alert]:
        """Check latency against rules."""
        for rule in self._rules.values():
            if rule.alert_type == AlertType.HIGH_LATENCY and rule.enabled:
                if rule.check(latency_ms):
                    return self.trigger(
                        alert_type=AlertType.HIGH_LATENCY,
                        severity=rule.severity,
                        message=rule.message_template.format(
                            value=latency_ms, node_id=node_id, threshold=rule.threshold
                        ),
                        node_id=node_id,
                        threshold=rule.threshold,
                        actual_value=latency_ms,
                    )
        return None

    def alert_node_failure(self, node_id: str, error: str) -> Alert:
        """Alert on node failure."""
        return self.trigger(
            alert_type=AlertType.NODE_FAILURE,
            severity=AlertSeverity.CRITICAL,
            message=f"Node {node_id} failed: {error}",
            node_id=node_id,
        )

    def alert_circuit_open(self, node_id: str) -> Alert:
        """Alert when circuit breaker opens."""
        return self.trigger(
            alert_type=AlertType.NODE_CIRCUIT_OPEN,
            severity=AlertSeverity.WARNING,
            message=f"Circuit breaker opened for node {node_id}",
            node_id=node_id,
        )

    def get_recent_alerts(
        self,
        limit: int = 20,
        severity: Optional[AlertSeverity] = None,
    ) -> List[Dict]:
        """Get recent alerts."""
        alerts = self._alerts[-limit:]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return [a.to_dict() for a in reversed(alerts)]

    def get_alert_counts(self) -> Dict[str, int]:
        """Get alert counts by type."""
        counts: Dict[str, int] = {}
        for alert in self._alerts:
            key = alert.alert_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


# Global singleton
alerting_system = AlertingSystem()
