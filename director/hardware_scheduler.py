"""
HardwareScheduler — GPU-aware scheduling constraints for habitat deployment.

Queries the graph to determine:
  - Which machines can run a given habitat
  - Whether a capability requires GPU resources
  - Which machines have the required GPUs available
"""

import logging

from director.models import BlueprintCandidate

logger = logging.getLogger("director.hardware_scheduler")


class MachineInfo:
    """Represents a machine's hardware capabilities."""

    __slots__ = ("name", "hostname", "cpu_cores", "ram_gb", "storage_gb", "cluster", "role", "gpus")

    def __init__(
        self,
        name: str,
        hostname: str = "",
        cpu_cores: int = 0,
        ram_gb: int = 0,
        storage_gb: int = 0,
        cluster: str = "",
        role: str = "",
        gpus: list[dict] | None = None,
    ):
        self.name = name
        self.hostname = hostname
        self.cpu_cores = cpu_cores
        self.ram_gb = ram_gb
        self.storage_gb = storage_gb
        self.cluster = cluster
        self.role = role
        self.gpus = gpus or []

    @property
    def has_gpu(self) -> bool:
        return any(g.get("vram_gb", 0) > 0 for g in self.gpus)

    @property
    def total_vram_gb(self) -> int:
        return sum(g.get("vram_gb", 0) * g.get("count", 1) for g in self.gpus)


class HardwareScheduler:
    """Determines which machines can run a given habitat blueprint."""

    def __init__(self, graph_store):
        self._graph = graph_store

    async def get_machines_for_blueprint(self, blueprint_name: str) -> list[dict]:
        """
        Find machines where a blueprint can run,
        ordered by scheduling preference (primary first).
        """
        query = """
        MATCH (h:HabitatBlueprint {name: $name})-[r:RUNS_ON]->(m:Machine)
        OPTIONAL MATCH (m)-[hg:HAS_GPU]->(g:GPU)
        RETURN m.name AS machine,
               m.hostname AS hostname,
               m.cpu_cores AS cpu,
               m.ram_gb AS ram,
               m.role AS role,
               r.preference AS preference,
               collect(DISTINCT {
                   gpu: g.name,
                   vram_gb: g.vram_gb,
                   count: hg.count
               }) AS gpus
        ORDER BY CASE r.preference WHEN 'primary' THEN 0 ELSE 1 END
        """
        results = await self._graph.execute_cypher(query, {"name": blueprint_name})
        logger.info(f"Blueprint '{blueprint_name}' can run on {len(results)} machine(s)")
        return results

    async def check_gpu_requirements(self, capabilities: list[str]) -> dict:
        """
        Check if any of the required capabilities need GPU resources.
        Returns: {needs_gpu: bool, required_gpus: [{name, vram_gb}]}
        """
        query = """
        UNWIND $capabilities AS cap_name
        MATCH (c:Capability {name: cap_name})-[:REQUIRES_GPU]->(g:GPU)
        RETURN DISTINCT g.name AS gpu_name, g.vram_gb AS vram_gb
        """
        results = await self._graph.execute_cypher(query, {"capabilities": capabilities})
        return {
            "needs_gpu": len(results) > 0,
            "required_gpus": [{"name": r["gpu_name"], "vram_gb": r["vram_gb"]} for r in results],
        }

    async def find_best_machine(
        self, blueprint: BlueprintCandidate, capabilities: list[str]
    ) -> dict | None:
        """
        Find the best machine for a blueprint considering GPU requirements.
        Returns machine info dict or None if no suitable machine found.
        """
        gpu_reqs = await self.check_gpu_requirements(capabilities)
        machines = await self.get_machines_for_blueprint(blueprint.name)

        if not machines:
            logger.warning(f"No machines found for {blueprint.name}")
            return None

        if not gpu_reqs["needs_gpu"]:
            # No GPU needed — return the primary preference machine
            best = machines[0]
            logger.info(f"Selected machine '{best['machine']}' (no GPU needed)")
            return best

        # GPU required — find a machine with adequate GPU
        min_vram = max((g["vram_gb"] for g in gpu_reqs["required_gpus"]), default=0)
        for machine in machines:
            for gpu in machine.get("gpus", []):
                if (gpu.get("vram_gb") or 0) >= min_vram and (gpu.get("count") or 0) > 0:
                    logger.info(
                        f"Selected machine '{machine['machine']}' "
                        f"with GPU {gpu['gpu']} ({gpu['vram_gb']}GB)"
                    )
                    return machine

        logger.warning(
            f"No machine with adequate GPU for {blueprint.name} (need {min_vram}GB VRAM)"
        )
        return None
