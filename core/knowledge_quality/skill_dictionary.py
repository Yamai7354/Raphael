"""
KQ-701 — Controlled Skill Vocabulary.

Skills can only enter Neo4j if they are in this dictionary
or explicitly added through the API. Loaded from data/skills.yaml.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger("core.knowledge_quality.skill_dictionary")

DICTIONARY_PATH = Path(__file__).parent.parent.parent / "data" / "skills.yaml"


@dataclass
class SkillEntry:
    """A single skill in the controlled vocabulary."""

    name: str
    category: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)


class SkillDictionary:
    """Loads and validates against the curated skill vocabulary."""

    def __init__(self, path: Path = DICTIONARY_PATH):
        self._skills: dict[str, SkillEntry] = {}
        self._alias_map: dict[str, str] = {}  # lowercase alias -> canonical name
        self._load(path)

    def _load(self, path: Path):
        if not path.exists():
            logger.warning("Skill dictionary not found at %s — using empty set", path)
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for entry in data.get("skills", []):
            se = SkillEntry(
                name=entry["name"],
                category=entry.get("category", ""),
                description=entry.get("description", ""),
                aliases=entry.get("aliases", []),
            )
            self._skills[se.name] = se
            for alias in se.aliases:
                self._alias_map[alias.lower()] = se.name
        logger.info("Loaded %d skills from dictionary", len(self._skills))

    def is_valid(self, name: str) -> bool:
        """Check if a skill name (or alias) is in the controlled vocabulary."""
        return name in self._skills or name.lower() in self._alias_map

    def canonicalize(self, name: str) -> str:
        """Return the canonical skill name for a name or alias."""
        if name in self._skills:
            return name
        return self._alias_map.get(name.lower(), name)

    def add(self, name: str, category: str = "", description: str = "") -> SkillEntry:
        """Runtime addition (caller should also update data/skills.yaml for persistence)."""
        se = SkillEntry(name=name, category=category, description=description)
        self._skills[name] = se
        return se

    def list_all(self) -> list[str]:
        """Return all canonical skill names, sorted."""
        return sorted(self._skills.keys())

    def get(self, name: str) -> SkillEntry | None:
        """Get a skill entry by canonical name."""
        return self._skills.get(name)

    def get_by_category(self, category: str) -> list[SkillEntry]:
        """Return all skills in a given category."""
        return [s for s in self._skills.values() if s.category == category]
