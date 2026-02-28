import argparse
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


ALLOWED_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".json",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".git",
    ".next",
    "node_modules",
    ".venv",
    ".npm-cache",
    "dist",
    "build",
    "coverage",
}


@dataclass
class Match:
    entity: str
    file: str
    line: int
    text: str


class RepoDiscoveryAgent:
    def __init__(self, root: Path):
        self.root = root
        self.patterns = {
            "agent": [
                re.compile(r"\bclass\s+([A-Za-z0-9_]*Agent[A-Za-z0-9_]*)\b"),
                re.compile(r"\b(?:const|let|var|type|interface)\s+([A-Za-z0-9_]*Agent[A-Za-z0-9_]*)\b"),
                re.compile(r"\"role\"\s*:\s*\"[^\"]*agent[^\"]*\"", re.IGNORECASE),
                re.compile(r"\btrigger_agent\b|\bstart-all\b|\bstart\s+agent\b", re.IGNORECASE),
            ],
            "skill": [
                re.compile(r"\"skills?\"\s*:\s*\[", re.IGNORECASE),
                re.compile(r"\bHAS_SKILL\b|\bskill\b", re.IGNORECASE),
                re.compile(r"/skills?/", re.IGNORECASE),
            ],
            "tool": [
                re.compile(r"\"tools?\"\s*:\s*\[", re.IGNORECASE),
                re.compile(r"\bUSES_TOOL\b|\btool\b", re.IGNORECASE),
                re.compile(r"\bterminal\b|\bprofiler\b|\bdebugger\b", re.IGNORECASE),
            ],
        }

    def _iter_files(self) -> Iterable[Path]:
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix.lower() in ALLOWED_EXTENSIONS:
                    yield path

    def scan(self, entity: str = "all", term: str | None = None) -> list[Match]:
        term_lc = term.lower() if term else None
        entities = ["agent", "skill", "tool"] if entity == "all" else [entity]
        matches: list[Match] = []

        for file_path in self._iter_files():
            rel = str(file_path.relative_to(self.root))
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for i, line in enumerate(content.splitlines(), start=1):
                trimmed = line.strip()
                if not trimmed:
                    continue
                if term_lc and term_lc not in trimmed.lower():
                    continue

                for current_entity in entities:
                    for pattern in self.patterns[current_entity]:
                        if pattern.search(trimmed):
                            matches.append(
                                Match(
                                    entity=current_entity,
                                    file=rel,
                                    line=i,
                                    text=trimmed[:220],
                                )
                            )
                            break
                    else:
                        continue
                    break

        return matches

    @staticmethod
    def summarize(matches: list[Match]) -> dict:
        summary = {"agent": 0, "skill": 0, "tool": 0}
        for match in matches:
            summary[match.entity] += 1
        return summary


def main():
    parser = argparse.ArgumentParser(description="Repo discovery agent for agents/tools/skills")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]), help="Repo root path")
    parser.add_argument(
        "--entity",
        choices=["all", "agent", "skill", "tool"],
        default="all",
        help="Entity category to search for",
    )
    parser.add_argument("--term", default=None, help="Optional substring filter")
    parser.add_argument("--limit", type=int, default=300, help="Max number of matches to emit")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    agent = RepoDiscoveryAgent(root)
    matches = agent.scan(entity=args.entity, term=args.term)
    payload = {
        "root": str(root),
        "entity": args.entity,
        "term": args.term,
        "summary": agent.summarize(matches),
        "total": len(matches),
        "matches": [asdict(m) for m in matches[: max(1, args.limit)]],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
