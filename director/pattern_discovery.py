"""
PatternDiscovery — Learns task→habitat patterns from the knowledge graph.

Phase 10: Autonomous Infrastructure

Capabilities:
  1. Pattern mining: discovers which problem types map to which habitats
  2. Chart generation: produces new Helm chart skeletons from patterns
  3. Confidence scoring: tracks pattern strength over time
"""

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger("director.pattern_discovery")


@dataclass
class DiscoveredPattern:
    """A discovered mapping: task type → optimal habitat."""

    task_type: str  # e.g. "code_generation", "research"
    best_blueprint: str
    agent_config: dict  # {agent_name: count}
    success_rate: float
    avg_completion_s: float
    sample_count: int
    confidence: float  # 0.0 to 1.0

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.7 and self.sample_count >= 5


class PatternDiscovery:
    """
    Mines the knowledge graph for task→habitat patterns
    and generates new Helm chart skeletons.
    """

    def __init__(self, graph_store):
        self._graph = graph_store
        self._patterns: dict[str, DiscoveredPattern] = {}

    async def discover_patterns(self) -> list[DiscoveredPattern]:
        """
        Mine the graph: for each capability, find the blueprint
        with the best PERFORMANCE metrics.
        """
        query = """
        MATCH (c:Capability)<-[:REQUIRES_CAPABILITY]-(h:HabitatBlueprint)
        OPTIONAL MATCH (h)-[:PERFORMANCE]->(m:Metric)
        WITH c.name AS capability,
             h.name AS blueprint,
             count(m) AS runs,
             avg(CASE WHEN m.success THEN 1.0 ELSE 0.0 END) AS success_rate,
             avg(m.completion_time_s) AS avg_time
        WHERE runs > 0
        RETURN capability, blueprint, runs, success_rate, avg_time
        ORDER BY capability, success_rate DESC, avg_time ASC
        """
        results = await self._graph.execute_cypher(query, {})

        # Group by capability, take the best blueprint
        patterns = {}
        for row in results:
            cap = row["capability"]
            if cap not in patterns:
                confidence = min(row["runs"] / 10.0, 1.0) * (row["success_rate"] or 0.0)
                patterns[cap] = DiscoveredPattern(
                    task_type=cap,
                    best_blueprint=row["blueprint"],
                    agent_config={},  # filled by agent query
                    success_rate=row["success_rate"] or 0.0,
                    avg_completion_s=row["avg_time"] or 0.0,
                    sample_count=row["runs"],
                    confidence=round(confidence, 3),
                )

        # Enrich with agent config
        for cap, pattern in patterns.items():
            agent_query = """
            MATCH (h:HabitatBlueprint {name: $blueprint})-[r:SPAWNS_AGENT]->(a:AgentType)
            RETURN a.name AS agent, r.count AS count, r.role AS role
            """
            agents = await self._graph.execute_cypher(
                agent_query, {"blueprint": pattern.best_blueprint}
            )
            pattern.agent_config = {
                a["agent"]: {"count": a["count"], "role": a["role"]} for a in agents
            }

        self._patterns = patterns
        logger.info(f"Discovered {len(patterns)} task→habitat pattern(s)")
        return list(patterns.values())

    def generate_helm_skeleton(self, pattern: DiscoveredPattern, output_dir: str) -> str:
        """
        Generate a Helm chart skeleton from a discovered pattern.
        Returns the path to the generated chart directory.
        """
        chart_name = f"{pattern.task_type}-habitat-auto"
        chart_dir = os.path.join(output_dir, chart_name)
        templates_dir = os.path.join(chart_dir, "templates")
        os.makedirs(templates_dir, exist_ok=True)

        # Chart.yaml
        chart_yaml = (
            f"apiVersion: v2\n"
            f"name: {chart_name}\n"
            f"description: Auto-generated from pattern: {pattern.task_type}\n"
            f"version: 0.1.0\n"
            f'appVersion: "auto"\n'
        )
        with open(os.path.join(chart_dir, "Chart.yaml"), "w") as f:
            f.write(chart_yaml)

        # values.yaml — render manually to avoid pyyaml dependency
        lines = ["# Auto-generated values", f"habitat:", f"  name: {chart_name}", "", "agents:"]
        for agent_name, config in pattern.agent_config.items():
            safe_name = agent_name.replace("_", "-")
            lines.extend(
                [
                    f"  {safe_name}:",
                    f"    replicas: {config.get('count', 1)}",
                    f"    role: {config.get('role', 'worker')}",
                    f"    image:",
                    f"      repository: raphael-registry:5111/{safe_name}",
                    f"      tag: latest",
                    f"    resources:",
                    f"      requests:",
                    f"        cpu: 100m",
                    f"        memory: 256Mi",
                    f"      limits:",
                    f"        cpu: 500m",
                    f"        memory: 512Mi",
                ]
            )
        with open(os.path.join(chart_dir, "values.yaml"), "w") as f:
            f.write("\n".join(lines) + "\n")

        # _helpers.tpl
        helpers = (
            '{{- define "chart.fullname" -}}\n{{ .Release.Name }}-' + chart_name + "\n{{- end }}\n"
        )
        with open(os.path.join(templates_dir, "_helpers.tpl"), "w") as f:
            f.write(helpers)

        # Generate a deployment template per agent
        for agent_name, config in pattern.agent_config.items():
            safe_name = agent_name.replace("_", "-")
            deployment = self._render_deployment(safe_name, config)
            with open(os.path.join(templates_dir, f"{safe_name}.yaml"), "w") as f:
                f.write(deployment)

        # service-discovery.yaml
        sd_data = {
            "pattern": pattern.task_type,
            "confidence": pattern.confidence,
            "agents": list(pattern.agent_config.keys()),
        }
        sd = (
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n"
            '  name: {{ include "chart.fullname" . }}-discovery\n'
            "data:\n"
            f"  manifest.json: |\n"
            f"    {json.dumps(sd_data, indent=4).replace(chr(10), chr(10) + '    ')}\n"
        )
        with open(os.path.join(templates_dir, "service-discovery.yaml"), "w") as f:
            f.write(sd)

        logger.info(f"Generated Helm chart skeleton: {chart_dir}")
        return chart_dir

    def _render_deployment(self, name: str, config: dict) -> str:
        """Render a Kubernetes Deployment YAML for an agent."""
        replicas = config.get("count", 1)
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{- include "chart.fullname" . }}}}-{name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
        role: {config.get("role", "worker")}
    spec:
      containers:
        - name: {name}
          image: {{{{ .Values.agents.{name}.image.repository }}}}:{{{{ .Values.agents.{name}.image.tag }}}}
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: {{{{ .Values.agents.{name}.resources.requests.cpu }}}}
              memory: {{{{ .Values.agents.{name}.resources.requests.memory }}}}
---
apiVersion: v1
kind: Service
metadata:
  name: {{{{- include "chart.fullname" . }}}}-{name}
spec:
  selector:
    app: {name}
  ports:
    - port: 8080
      targetPort: 8080
"""

    def get_pattern(self, task_type: str) -> DiscoveredPattern | None:
        """Look up a discovered pattern by task type."""
        return self._patterns.get(task_type)

    @property
    def reliable_patterns(self) -> list[DiscoveredPattern]:
        """Return only high-confidence patterns."""
        return [p for p in self._patterns.values() if p.is_reliable]
