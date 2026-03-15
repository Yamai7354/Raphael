"""
KQ-702 — Tool Manifest Registry.

Only tools with a valid manifest can create Tool nodes,
REQUIRES_CAPABILITY edges, and input/output schema nodes in Neo4j.
Loaded from data/tool_manifests/*.yaml|*.json.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("core.knowledge_quality.tool_manifests")

MANIFESTS_DIR = Path(__file__).parent.parent.parent / "data" / "tool_manifests"


@dataclass
class ToolManifest:
    """Parsed tool manifest."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    requires_capabilities: list[str] = field(default_factory=list)
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    tool_type: str = "custom"
    timeout_sec: float = 30.0
    allowed_roles: list[str] = field(default_factory=list)
    source_file: str = ""


class ToolManifestRegistry:
    """Loads and queries tool manifests from YAML/JSON files."""

    def __init__(self, manifests_dir: Path = MANIFESTS_DIR):
        self._manifests: dict[str, ToolManifest] = {}
        self._load_all(manifests_dir)

    def _load_all(self, directory: Path):
        if not directory.exists():
            logger.warning("Tool manifests directory not found: %s", directory)
            return
        files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.json"))
        for path in files:
            try:
                self._load_file(path)
            except Exception as e:
                logger.error("Failed to load manifest %s: %s", path, e)
        logger.info("Loaded %d tool manifests", len(self._manifests))

    def _load_file(self, path: Path):
        with open(path) as f:
            if path.suffix == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)

        manifests = data if isinstance(data, list) else [data]
        for m in manifests:
            tm = ToolManifest(
                name=m["name"],
                description=m.get("description", ""),
                version=m.get("version", "1.0.0"),
                requires_capabilities=m.get("requires_capabilities", []),
                inputs=m.get("inputs", {}),
                outputs=m.get("outputs", {}),
                tool_type=m.get("tool_type", "custom"),
                timeout_sec=m.get("timeout_sec", 30.0),
                allowed_roles=m.get("allowed_roles", []),
                source_file=str(path),
            )
            self._manifests[tm.name] = tm

    def has_manifest(self, name: str) -> bool:
        """Check if a tool has a registered manifest."""
        return name in self._manifests

    def get(self, name: str) -> ToolManifest | None:
        """Get a tool manifest by name."""
        return self._manifests.get(name)

    def list_all(self) -> list[str]:
        """Return all registered tool names, sorted."""
        return sorted(self._manifests.keys())

    def get_capabilities_for(self, name: str) -> list[str]:
        """Return the capabilities required by a tool."""
        tm = self._manifests.get(name)
        return tm.requires_capabilities if tm else []
