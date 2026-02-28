"""
KQ-611 — Knowledge Quality Dashboard.

Aggregates data from all KQ subsystems: confidence distribution,
contradiction alerts, top agents, knowledge growth trends.
"""

import logging

logger = logging.getLogger("core.knowledge_quality.dashboard")


class QualityDashboard:
    """Aggregates knowledge quality metrics for visualization."""

    def __init__(
        self,
        scoring=None,
        evidence=None,
        contradictions=None,
        validation=None,
        noise=None,
        lifecycle=None,
        reputation=None,
        embedding=None,
        propagation=None,
        reviews=None,
        redundancy=None,
        drift=None,
        value=None,
    ):
        self.scoring = scoring
        self.evidence = evidence
        self.contradictions = contradictions
        self.validation = validation
        self.noise = noise
        self.lifecycle = lifecycle
        self.reputation = reputation
        self.embedding = embedding
        self.propagation = propagation
        self.reviews = reviews
        self.redundancy = redundancy
        self.drift = drift
        self.value = value

    def get_dashboard(self) -> dict:
        """Full dashboard data."""
        data: dict = {}

        if self.scoring:
            data["quality_scores"] = self.scoring.get_stats()
        if self.evidence:
            data["evidence"] = self.evidence.get_stats()
        if self.contradictions:
            data["contradictions"] = self.contradictions.get_stats()
            data["open_contradictions"] = [c.to_dict() for c in self.contradictions.get_open()[:10]]
        if self.validation:
            data["validation"] = self.validation.get_stats()
        if self.noise:
            data["noise_reduction"] = self.noise.get_stats()
        if self.lifecycle:
            data["lifecycle"] = self.lifecycle.get_stats()
        if self.reputation:
            data["top_agents"] = [r.to_dict() for r in self.reputation.get_top_agents(5)]
            data["low_performers"] = [r.to_dict() for r in self.reputation.get_low_performers()]
        if self.embedding:
            data["embedding"] = self.embedding.get_stats()
        if self.propagation:
            data["confidence_graph"] = self.propagation.get_stats()
        if self.reviews:
            data["reviews"] = self.reviews.get_stats()
        if self.redundancy:
            data["redundancy"] = self.redundancy.get_stats()
        if self.drift:
            data["drift"] = self.drift.get_stats()
        if self.value:
            data["value_scoring"] = self.value.get_stats()

        return data

    def get_alerts(self) -> list[dict]:
        """Urgent items needing attention."""
        alerts: list[dict] = []

        if self.contradictions:
            open_ct = self.contradictions.get_open()
            if open_ct:
                alerts.append(
                    {
                        "type": "contradictions",
                        "severity": "warning",
                        "message": f"{len(open_ct)} unresolved contradictions",
                    }
                )

        if self.reputation:
            low = self.reputation.get_low_performers()
            if low:
                alerts.append(
                    {
                        "type": "low_reputation_agents",
                        "severity": "info",
                        "message": f"{len(low)} agents with low reputation",
                    }
                )

        if self.scoring:
            stats = self.scoring.get_stats()
            below = stats.get("below_030", 0)
            if below > 10:
                alerts.append(
                    {
                        "type": "low_quality_knowledge",
                        "severity": "warning",
                        "message": f"{below} knowledge nodes below quality threshold",
                    }
                )

        return alerts

    def get_stats(self) -> dict:
        return {
            "subsystems_connected": sum(
                1
                for x in [
                    self.scoring,
                    self.evidence,
                    self.contradictions,
                    self.validation,
                    self.noise,
                    self.lifecycle,
                    self.reputation,
                    self.embedding,
                    self.propagation,
                    self.reviews,
                    self.redundancy,
                    self.drift,
                    self.value,
                ]
                if x is not None
            )
        }
