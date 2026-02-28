# Title: Self-Evolving Multi-Cultural Swarm with Agent Recycling
# Updated with Agent Registry, KG Linking, and Migration to Agent_Society
# Refactored to use httpx (standard in project) and optional visualization

import os
import random
import json
import base64
import hashlib
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Optional Visualization
try:
    import networkx as nx
    import matplotlib.pyplot as plt

    HAS_VIZ = True
except ImportError:
    HAS_VIZ = False
    print("Optimization: networkx/matplotlib not found. Visualization disabled.")

# Load environment variables
load_dotenv()

# --- Config ---
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7693")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Agent_Society Graph for retired agents
SOCIETY_URI = "bolt://127.0.0.1:7694"

# Ollama / OpenAI Setup
# Using the local node URL for Ollama
OLLAMA_LOCAL_URL = os.getenv("OLLAMA_LOCAL_URL", "http://100.125.58.22:5000")
API_BASE_URL = f"{OLLAMA_LOCAL_URL.rstrip('/')}/v1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_SCRIPT = PROJECT_ROOT / "app" / "memory_system.py"
PYTHON_BIN = PROJECT_ROOT / ".venv" / "bin" / "python"
MODEL_SYNC_REPORT = PROJECT_ROOT / "data" / "model_sync_report.json"
AGENT_REGISTRY_PATH = PROJECT_ROOT / "data" / "agents.json"
MEMORY_DB_PATH = PROJECT_ROOT / "data" / "memory_system.db"
DISCOVERY_LOG_PATH = PROJECT_ROOT / "data" / "discovery_archival_log.json"
DISCOVERY_REPUTATION_PATH = PROJECT_ROOT / "data" / "discovery_reputation.json"
DISCOVERY_POLICY_PATH = PROJECT_ROOT / "data" / "discovery_policy.json"
PRIORITY_STATE_PATH = PROJECT_ROOT / "data" / "swarm_priority_state.json"
PRIORITY_COMMAND_PATH = PROJECT_ROOT / "data" / "swarm_priority_command.json"
AGENT_MISSIONS_PATH = PROJECT_ROOT / "data" / "agent_missions.json"

MOODS = ["Calm", "Curious", "Excited", "Cautious"]
BOREDOM_MISSIONS = [
    "improve retrieval accuracy",
    "reduce response latency",
    "discover new models",
    "optimize memory compression",
    "design new agents",
]

# --- Multi-Cultural Name Pools ---
NAME_POOLS = {
    "Japanese": {
        "Researcher": ["Satoru", "Akira", "Yuki", "Hina"],
        "Analyst": ["Kenji", "Hikaru", "Takashi", "Mio"],
        "Creative Coder": ["Riku", "Haruto", "Kaito", "Sora"],
        "Communicator": ["Aiko", "Sayuri", "Yui", "Ren"],
        "Explorer": ["Takumi", "Shun", "Daiki", "Kouta"],
    },
    "Chinese": {
        "Researcher": ["Wei", "Jun", "Chen", "Lin"],
        "Analyst": ["Jian", "Shu", "Hao", "Lei"],
        "Creative Coder": ["Ming", "Kai", "Bo", "Yi"],
        "Communicator": ["Lian", "Mei", "Xi", "An"],
        "Explorer": ["Tao", "Feng", "Yang", "Long"],
    },
    "Korean": {
        "Researcher": ["Joon", "Minho", "Jiwoo", "Soobin"],
        "Analyst": ["Dong", "Seok", "Yoon", "Hee"],
        "Creative Coder": ["Jiho", "Tae", "Jin", "Kook"],
        "Communicator": ["Hana", "Soo", "Ara", "Bora"],
        "Explorer": ["Seung", "Hyunwoo", "Min", "Kyung"],
    },
    "Vietnamese": {
        "Researcher": ["Minh", "Quang", "Duy", "Huy"],
        "Analyst": ["An", "Khanh", "Tuan", "Hoang"],
        "Creative Coder": ["Hai", "Nam", "Son", "Phuc"],
        "Communicator": ["Lan", "Huong", "Trang", "Linh"],
        "Explorer": ["Viet", "Trung", "Binh", "Thanh"],
    },
    "Thai": {
        "Researcher": ["Niran", "Chai", "Arun", "Boon"],
        "Analyst": ["Anurak", "Krit", "Pravat", "Somsak"],
        "Creative Coder": ["Kritsana", "Nattapong", "Phichit", "Sakda"],
        "Communicator": ["Malee", "Nok", "Ratana", "Siriporn"],
        "Explorer": ["Somchai", "Kittisak", "Viroj", "Wanchai"],
    },
}
CULTURE_ORDER = ["Japanese", "Chinese", "Korean", "Vietnamese", "Thai"]


# --- Name Manager ---
class NameManager:
    def __init__(self):
        self.used_names = set()
        self.culture_order = CULTURE_ORDER
        self.current_culture_index = 0

    def get_name(self, role):
        start_index = self.current_culture_index
        while True:
            culture = self.culture_order[self.current_culture_index]
            pool = NAME_POOLS[culture][role]
            available = [n for n in pool if n not in self.used_names]
            if available:
                name = random.choice(available)
                self.used_names.add(name)
                return name, culture
            else:
                self.current_culture_index = (self.current_culture_index + 1) % len(
                    self.culture_order
                )
                if self.current_culture_index == start_index:
                    # Looped back, try a random name with a suffix if absolutely deadlocked
                    name = f"{random.choice(pool)}_{random.randint(100, 999)}"
                    return name, culture


# --- LLM Character Generator (using httpx) ---
def generate_character_with_llm(name, role, culture, model_name="l3-8b-stheno-v3.2-iq-imatrix"):
    prompt = f"""
    Generate a JSON agent character for the Raphael Swarm.
    Name: {name}
    Role: {role}
    Culture: {culture}
    
    Return EXACT JSON with these keys:
    "personality_traits": [list of 5 traits],
    "personality_type": "One word type (e.g. Architect, Visionary)",
    "quirks": [list of 1-2 quirks],
    "dialogue_style": {{ "tone": "string", "vocabulary": "string" }},
    "backstory": "1-2 sentences",
    "motivations": "Main goal",
    "skills": [list of 3 relevant skills],
    "tools": [list of 2 relevant tools]
    """
    try:
        url = f"{API_BASE_URL}/chat/completions"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=6.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as e:
        print(f"LLM Error: {e}. Using fallback.")
        return {
            "personality_traits": ["Diligent", "Curious", "Punctual", "Resourceful", "Loyal"],
            "personality_type": "Specialist",
            "quirks": ["Humming while working"],
            "dialogue_style": {"tone": "Professional", "vocabulary": "Technical"},
            "backstory": f"{name} was initialized to support the {role} layer.",
            "motivations": "Optimize swarm efficiency",
            "skills": ["Analysis", "Reporting", "Verification"],
            "tools": ["Terminal", "Debugger"],
        }


def _load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def _list_ollama_models():
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
        lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        if len(lines) <= 1:
            return []
        models = []
        for ln in lines[1:]:
            name = ln.split()[0].strip()
            if name:
                models.append(name)
        seen = set()
        unique = []
        for m in models:
            if m not in seen:
                seen.add(m)
                unique.append(m)
        return unique
    except Exception:
        return []


def _pick_by_patterns(candidates, patterns, fallback):
    for pat in patterns:
        for model in candidates:
            if pat in model.lower():
                return model
    return fallback


def load_model_assignments():
    report = _load_json(MODEL_SYNC_REPORT, {})
    assignments = report.get("assignments", {}) if isinstance(report, dict) else {}
    if isinstance(assignments, dict) and assignments:
        return {str(k).strip(): str(v).strip() for k, v in assignments.items() if str(k).strip() and str(v).strip()}
    registry = _load_json(AGENT_REGISTRY_PATH, {"agents": []})
    mapping = {}
    for agent in registry.get("agents", []):
        if isinstance(agent, dict) and str(agent.get("name", "")).strip() and str(agent.get("model", "")).strip():
            mapping[str(agent["name"]).strip()] = str(agent["model"]).strip()
    return mapping


MODEL_ASSIGNMENTS = load_model_assignments()
OLLAMA_MODELS = _list_ollama_models()


def pick_task_model(task_type: str, fallback: str):
    candidates = [m for m in OLLAMA_MODELS if "embedding" not in m.lower() and "embed" not in m.lower() and "whisper" not in m.lower() and "moondream" not in m.lower()]
    if not candidates:
        return fallback
    task = (task_type or "").lower()
    if task == "experiment":
        return _pick_by_patterns(candidates, ["ministral", "l3-8b-stheno", "stheno"], fallback)
    if task == "communication":
        return _pick_by_patterns(candidates, ["l3-8b-stheno", "stheno", "ministral"], fallback)
    if task == "validation":
        return _pick_by_patterns(candidates, ["ministral", "l3-8b-stheno", "stheno"], fallback)
    return _pick_by_patterns(candidates, ["l3-8b-stheno", "stheno", "ministral"], fallback)


def _utc_now():
    return datetime.now(timezone.utc)


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _token_set(text):
    return {tok for tok in str(text or "").lower().replace("|", " ").replace("-", " ").split() if tok}


def _text_similarity(a, b):
    at = _token_set(a)
    bt = _token_set(b)
    if not at or not bt:
        return 0.0
    return len(at & bt) / len(at | bt)


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except Exception:
        return fallback


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _atomic_write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2))
    os.replace(tmp_path, path)


def _call_memory_action(action: str, payload: dict | None = None):
    if not MEMORY_SCRIPT.exists() or not PYTHON_BIN.exists():
        return {"ok": False, "error": "memory runtime missing"}
    encoded = base64.b64encode(json.dumps(payload or {}).encode("utf-8")).decode("utf-8")
    try:
        result = subprocess.run(
            [str(PYTHON_BIN), str(MEMORY_SCRIPT), "--action", action, "--payload-b64", encoded],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return json.loads(result.stdout) if result.stdout.strip() else {"ok": False, "error": "empty memory response"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _load_reputation():
    data = _read_json(DISCOVERY_REPUTATION_PATH, {"agents": {}, "history": []})
    if not isinstance(data, dict):
        data = {"agents": {}, "history": []}
    if not isinstance(data.get("agents"), dict):
        data["agents"] = {}
    if not isinstance(data.get("history"), list):
        data["history"] = []
    return data


def _award_reputation(explorer: str, reviewer: str, archivist: str, score: float):
    rep = _load_reputation()
    rewards = {
        explorer: round(10 + (score * 10), 2),
        reviewer: round(6 + (score * 7), 2),
        archivist: round(8 + (score * 8), 2),
    }
    for agent_name, points in rewards.items():
        rep["agents"][agent_name] = round(float(rep["agents"].get(agent_name, 0)) + points, 2)
    rep["history"].append(
        {
            "time": _utc_now().isoformat(),
            "explorer": explorer,
            "reviewer": reviewer,
            "archivist": archivist,
            "score": round(score, 4),
            "rewards": rewards,
        }
    )
    rep["history"] = rep["history"][-3000:]
    _write_json(DISCOVERY_REPUTATION_PATH, rep)
    return rewards


class DiscoveryPipeline:
    max_new_memories_per_hour = 50
    consolidation_interval_hours = 3

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.last_consolidation_at = _utc_now() - timedelta(hours=self.consolidation_interval_hours)
        self._persist_policy()

    def _persist_policy(self):
        _write_json(
            DISCOVERY_POLICY_PATH,
            {
                "groups": ["Explorers", "Reviewers", "Archivists"],
                "max_new_memories_per_hour": self.max_new_memories_per_hour,
                "store_threshold": 0.7,
                "scoring": {
                    "novelty": 0.35,
                    "usefulness": 0.35,
                    "source_quality": 0.2,
                    "swarm_interest": 0.1,
                },
                "graph_shape": "Topic -> Concept -> Evidence",
            },
        )

    def _load_archival_log(self):
        data = _read_json(DISCOVERY_LOG_PATH, {"events": []})
        events = data.get("events", []) if isinstance(data, dict) else []
        return [e for e in events if isinstance(e, dict) and "time" in e]

    def _save_archival_log(self, events):
        _write_json(DISCOVERY_LOG_PATH, {"events": events[-5000:]})

    def _archived_last_hour(self):
        cutoff = _utc_now() - timedelta(hours=1)
        count = 0
        for event in self._load_archival_log():
            try:
                if datetime.fromisoformat(event["time"]) >= cutoff:
                    count += 1
            except Exception:
                continue
        return count

    def _record_archival(self, evidence_id, explorer, reviewer, archivist, score):
        events = self._load_archival_log()
        events.append(
            {
                "time": _utc_now().isoformat(),
                "evidence_id": evidence_id,
                "explorer": explorer,
                "reviewer": reviewer,
                "archivist": archivist,
                "score": round(score, 4),
            }
        )
        self._save_archival_log(events)

    def _groups(self, agents):
        explorers = [a for a in agents if a.role in {"Researcher", "Explorer"}]
        reviewers = [a for a in agents if a.role in {"Analyst", "Communicator"}]
        archivists = [a for a in agents if a.role in {"Creative Coder"}]
        pool = list(agents)
        if not explorers and pool:
            explorers = [pool[0]]
        if not reviewers and len(pool) > 1:
            reviewers = [pool[1]]
        if not archivists and len(pool) > 2:
            archivists = [pool[2]]
        if not reviewers and explorers:
            reviewers = [explorers[0]]
        if not archivists and reviewers:
            archivists = [reviewers[0]]
        return explorers, reviewers, archivists

    def build_exploration_event(self, agent, task_type, concept, success):
        topic = f"{agent.role}:{task_type}"
        notes = f"{agent.name} observed {concept} with mood={agent.mood} model={agent.model} success={success}"
        sources = [f"agent://{agent.name}", f"model://{agent.model}"]
        novelty_estimate = _clamp(0.45 + random.random() * 0.5 + (0.1 if success else -0.1), 0.0, 1.0)
        confidence = _clamp(agent.task_success_rate, 0.0, 1.0)
        return {
            "id": hashlib.md5(f"{agent.name}|{topic}|{concept}|{_utc_now().isoformat()}".encode("utf-8")).hexdigest()[:16],
            "agent": agent.name,
            "topic": topic,
            "notes": notes,
            "sources": sources,
            "confidence": round(confidence, 4),
            "novelty_estimate": round(novelty_estimate, 4),
            "concept": concept,
        }

    def review(self, events, reviewer_name):
        clusters = []
        used = set()
        for i, event in enumerate(events):
            if i in used:
                continue
            cluster = [event]
            used.add(i)
            for j in range(i + 1, len(events)):
                if j in used:
                    continue
                if _text_similarity(event["topic"], events[j]["topic"]) > 0.55 or _text_similarity(event["notes"], events[j]["notes"]) > 0.6:
                    cluster.append(events[j])
                    used.add(j)
            clusters.append(cluster)

        reviewed = []
        for cluster in clusters:
            base = cluster[0]
            novelty = _clamp(sum(e["novelty_estimate"] for e in cluster) / len(cluster), 0.0, 1.0)
            usefulness = _clamp(sum(e["confidence"] for e in cluster) / len(cluster), 0.0, 1.0)
            source_quality = _clamp(len({s for e in cluster for s in e["sources"]}) / 4.0, 0.0, 1.0)
            swarm_interest = _clamp(min(1.0, len(cluster) / 4.0), 0.0, 1.0)
            final_score = (novelty * 0.35) + (usefulness * 0.35) + (source_quality * 0.2) + (swarm_interest * 0.1)
            reviewed.append(
                {
                    "cluster_id": hashlib.md5("|".join(sorted(e["id"] for e in cluster)).encode("utf-8")).hexdigest()[:16],
                    "topic": base["topic"],
                    "concept": base["concept"],
                    "cluster_size": len(cluster),
                    "events": cluster,
                    "reviewer": reviewer_name,
                    "scores": {
                        "novelty": round(novelty, 4),
                        "usefulness": round(usefulness, 4),
                        "source_quality": round(source_quality, 4),
                        "swarm_interest": round(swarm_interest, 4),
                        "final_score": round(final_score, 4),
                    },
                    "create_embedding": final_score > 0.8,
                    "store": final_score > 0.7,
                    "duplicate_detected": len(cluster) > 1,
                }
            )
        return reviewed

    def _topic_concept_evidence_graph(self, topic, concept, evidence_id, summary, source_agent, score):
        try:
            driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
        except Exception:
            return
        try:
            with driver.session() as session:
                session.run(
                    """
                    MERGE (t:Topic {name: $topic})
                    MERGE (c:Concept {name: $concept})
                    ON CREATE SET c.created_at = datetime()
                    SET c.updated_at = datetime()
                    MERGE (e:Evidence {id: $evidence_id})
                    SET e.summary = $summary,
                        e.source_agent = $source_agent,
                        e.score = $score,
                        e.created_at = datetime()
                    MERGE (t)-[:HAS_CONCEPT]->(c)
                    MERGE (c)-[:SUPPORTED_BY]->(e)
                    MERGE (a:Agent {name: $source_agent})
                    MERGE (a)-[:DISCOVERED]->(e)
                    """,
                    topic=topic,
                    concept=concept,
                    evidence_id=evidence_id,
                    summary=summary[:400],
                    source_agent=source_agent,
                    score=float(score),
                )
        except Exception:
            pass
        finally:
            try:
                driver.close()
            except Exception:
                pass

    def _consolidate(self):
        _call_memory_action("consolidate", {"window_days": 7, "min_items": 5})
        _call_memory_action("retention", {"keep_days": 90, "confidence_threshold": 0.35})
        _call_memory_action("conflicts", {"limit": 20000})
        try:
            driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
            with driver.session() as session:
                session.run(
                    """
                    MATCH (e:Evidence)
                    WHERE coalesce(e.score, 0.0) < 0.45
                    WITH e LIMIT 500
                    DETACH DELETE e
                    """
                )
        except Exception:
            pass
        finally:
            try:
                driver.close()
            except Exception:
                pass
        self.last_consolidation_at = _utc_now()

    def maybe_run_consolidation_cycle(self):
        if _utc_now() - self.last_consolidation_at >= timedelta(hours=self.consolidation_interval_hours):
            self._consolidate()
            return True
        return False

    def process_discoveries(self, agents, exploration_events):
        explorers, reviewers, archivists = self._groups(agents)
        if not exploration_events or not reviewers or not archivists:
            return []
        reviewer = reviewers[0]
        reviewed = self.review(exploration_events, reviewer.name)
        feed = []
        stored = 0
        for entry in reviewed:
            if not entry["store"]:
                feed.append(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "type": "Observation",
                        "summary": f"Reviewer {reviewer.name} rejected cluster {entry['cluster_id']} score={entry['scores']['final_score']:.2f}",
                    }
                )
                continue

            if self._archived_last_hour() >= self.max_new_memories_per_hour:
                self._consolidate()
                feed.append(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "type": "Observation",
                        "summary": "Memory cap reached (50/hr). Running consolidation and optimization instead of storing new memories.",
                    }
                )
                break

            archivist = archivists[stored % len(archivists)]
            summary = f"{entry['topic']} :: {entry['concept']} ({entry['cluster_size']} observations)"
            memory_query = _call_memory_action("query", {"q": f"{entry['topic']} {entry['concept']}", "k": 1})
            supersedes_id = None
            existing_items = memory_query.get("items", []) if isinstance(memory_query, dict) else []
            if existing_items:
                top = existing_items[0]
                if float(top.get("score", 0.0)) >= 0.86:
                    supersedes_id = top.get("id")

            payload = {
                "intent": "research insight",
                "memory_type": "semantic",
                "source_agent": entry["events"][0]["agent"],
                "summary": summary,
                "content": "\n".join([ev["notes"] for ev in entry["events"]][:6]),
                "confidence": _clamp(entry["scores"]["final_score"], 0.0, 1.0),
                "validation_status": "verified" if entry["scores"]["final_score"] >= 0.82 else "unverified",
                "create_embedding": bool(entry["create_embedding"]),
                "supersedes_id": supersedes_id,
                "metadata": {
                    "pipeline": "discovery_economy",
                    "topic": entry["topic"],
                    "concepts": [entry["concept"], entry["topic"]],
                    "reviewer": reviewer.name,
                    "archivist": archivist.name,
                    "cluster_size": entry["cluster_size"],
                    "claim_key": f"{entry['topic']}::{entry['concept']}",
                    "stance": "positive",
                    "source_quality": entry["scores"]["source_quality"],
                },
            }
            write_result = _call_memory_action("write", payload)
            if write_result.get("ok"):
                memory_item = write_result.get("item", {})
                evidence_id = str(memory_item.get("id", entry["cluster_id"]))
                self._topic_concept_evidence_graph(
                    topic=entry["topic"],
                    concept=entry["concept"],
                    evidence_id=evidence_id,
                    summary=summary,
                    source_agent=entry["events"][0]["agent"],
                    score=entry["scores"]["final_score"],
                )
                rewards = _award_reputation(
                    explorer=entry["events"][0]["agent"],
                    reviewer=reviewer.name,
                    archivist=archivist.name,
                    score=entry["scores"]["final_score"],
                )
                self._record_archival(
                    evidence_id=evidence_id,
                    explorer=entry["events"][0]["agent"],
                    reviewer=reviewer.name,
                    archivist=archivist.name,
                    score=entry["scores"]["final_score"],
                )
                stored += 1
                feed.append(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "type": "Task",
                        "summary": (
                            f"Discovery archived by {archivist.name}: {entry['concept']} "
                            f"(score={entry['scores']['final_score']:.2f}, embed={entry['create_embedding']}) "
                            f"Rewards -> {entry['events'][0]['agent']}+{rewards[entry['events'][0]['agent']]:.1f}, "
                            f"{reviewer.name}+{rewards[reviewer.name]:.1f}, {archivist.name}+{rewards[archivist.name]:.1f}"
                        ),
                    }
                )
            else:
                feed.append(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "type": "Observation",
                        "summary": f"Archivist {archivist.name} failed to store cluster {entry['cluster_id']}",
                    }
                )
        return feed


class SwarmPriorityEngine:
    """
    Periodically asks "what is best for the system right now?" and applies adaptive actions.
    """

    interval_seconds = 180
    max_agents = 24

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.last_eval_monotonic = 0.0
        self.history = _read_json(PRIORITY_STATE_PATH, {"evaluations": []})
        if not isinstance(self.history, dict):
            self.history = {"evaluations": []}
        if not isinstance(self.history.get("evaluations"), list):
            self.history["evaluations"] = []
        self.missions = _read_json(AGENT_MISSIONS_PATH, {"agents": {}, "history": []})
        if not isinstance(self.missions, dict):
            self.missions = {"agents": {}, "history": []}
        if not isinstance(self.missions.get("agents"), dict):
            self.missions["agents"] = {}
        if not isinstance(self.missions.get("history"), list):
            self.missions["history"] = []

    def should_run(self) -> bool:
        if PRIORITY_COMMAND_PATH.exists():
            return True
        return (time.monotonic() - self.last_eval_monotonic) >= self.interval_seconds

    def _save(self):
        self.history["evaluations"] = self.history.get("evaluations", [])[-500:]
        _write_json(PRIORITY_STATE_PATH, self.history)

    def _save_missions(self):
        self.missions["history"] = self.missions.get("history", [])[-2000:]
        _write_json(AGENT_MISSIONS_PATH, self.missions)

    def _consume_manual_command(self):
        payload = _read_json(PRIORITY_COMMAND_PATH, {})
        try:
            PRIORITY_COMMAND_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        if not isinstance(payload, dict):
            return None
        action = str(payload.get("action", "")).strip()
        allowed = {
            "spawn_compression_agents",
            "spawn_evaluators",
            "spawn_coding_agents",
            "allow_research_mode",
            "maintain",
            "assign_boredom_missions",
        }
        return action if action in allowed else None

    def _apply_action(self, swarm, action: str) -> tuple[int, str]:
        spawned = 0
        details = "System balanced; no intervention needed."
        if action == "spawn_compression_agents":
            spawned = self._spawn(swarm, "Analyst", 1) + self._spawn(swarm, "Creative Coder", 1)
            details = "Graph too large; compression specialists activated."
        elif action == "spawn_evaluators":
            spawned = self._spawn(swarm, "Analyst", 1)
            details = "Memory quality dropping; evaluator activated."
        elif action == "spawn_coding_agents":
            spawned = self._spawn(swarm, "Creative Coder", 1)
            details = "Feature throughput low; coding specialist activated."
        elif action == "allow_research_mode":
            spawned = self._spawn(swarm, "Explorer", 1)
            details = "System idle; research mode expanded."
        elif action == "assign_boredom_missions":
            details = "Mission assignment requested for bored agents."
        return spawned, details

    def _is_bored(self, agent) -> bool:
        history = getattr(agent, "task_history", [])
        if not isinstance(history, list) or len(history) < 6:
            return False
        recent = history[-6:]
        kinds = {item.get("task") for item in recent if isinstance(item, dict)}
        success_ratio = sum(1 for item in recent if item.get("success")) / max(1, len(recent))
        repetitive = len(kinds) <= 1
        stable_mood = str(getattr(agent, "mood", "")).lower() in {"calm", "cautious"}
        return repetitive and stable_mood and success_ratio >= 0.5

    def _assign_boredom_missions(self, swarm, force: bool = False) -> list[dict]:
        now = _utc_now().isoformat()
        active_names = {a.name for a in swarm.agents}
        current_agents = self.missions.get("agents", {})
        self.missions["agents"] = {name: data for name, data in current_agents.items() if name in active_names}
        feed = []
        for idx, agent in enumerate(swarm.agents):
            if self.missions["agents"].get(agent.name, {}).get("mission"):
                agent.current_mission = self.missions["agents"][agent.name]["mission"]
                continue
            if not (force or self._is_bored(agent)):
                continue
            mission = BOREDOM_MISSIONS[idx % len(BOREDOM_MISSIONS)]
            assignment = {
                "mission": mission,
                "assigned_at": now,
                "reason": "manual" if force else "boredom",
            }
            self.missions["agents"][agent.name] = assignment
            self.missions["history"].append({"agent": agent.name, **assignment})
            agent.current_mission = mission
            feed.append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "Observation",
                    "summary": f"Mission assigned -> {agent.name}: {mission}",
                }
            )
        if feed:
            self._save_missions()
        return feed

    def get_active_missions(self):
        agents = self.missions.get("agents", {})
        if not isinstance(agents, dict):
            return {}
        return {
            name: str(payload.get("mission", "")).strip()
            for name, payload in agents.items()
            if isinstance(payload, dict) and str(payload.get("mission", "")).strip()
        }

    def _graph_pressure(self) -> tuple[bool, dict]:
        try:
            driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
            with driver.session() as session:
                nodes = int(session.run("MATCH (n) RETURN count(n) AS c").single()["c"])
                rels = int(session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"])
            driver.close()
            overloaded = nodes > 120_000 or rels > 3_500_000
            return overloaded, {"nodes": nodes, "relationships": rels}
        except Exception:
            return False, {"nodes": None, "relationships": None}

    def _memory_quality_dropping(self) -> tuple[bool, dict]:
        health = _call_memory_action("health", {})
        trace = _call_memory_action("trace", {"window_days": 1})
        avg_conf = 0.0
        conflict_items = 0
        hit_rate = 100.0
        if health.get("ok"):
            h = health.get("health", {})
            avg_conf = float(h.get("avg_confidence", 0.0))
            conflict_items = int(h.get("conflict_items", 0))
        if trace.get("ok"):
            t = trace.get("trace", {})
            hit_rate = float(t.get("hit_rate_pct", 100.0))
        dropping = avg_conf < 0.55 or conflict_items > 1200 or hit_rate < 60.0
        return dropping, {"avg_confidence": avg_conf, "conflict_items": conflict_items, "hit_rate_pct": hit_rate}

    def _no_new_features(self, recent_feed: list[dict]) -> bool:
        text = " ".join(str(item.get("summary", "")).lower() for item in recent_feed[-80:])
        feature_tokens = ["feature", "implement", "build", "refactor", "fix", "ship"]
        return not any(tok in text for tok in feature_tokens)

    def _system_idle(self, agents: list) -> bool:
        active = sum(1 for a in agents if getattr(a, "task_success_rate", 0.0) > 0.01)
        return active == 0 or len(agents) < 3

    def _spawn(self, swarm, role: str, count: int) -> int:
        if len(swarm.agents) >= self.max_agents:
            return 0
        spawned = 0
        for _ in range(max(0, count)):
            if len(swarm.agents) >= self.max_agents:
                break
            swarm.add_agent(role)
            spawned += 1
        return spawned

    def evaluate_and_apply(self, swarm, recent_feed: list[dict]) -> list[dict]:
        now = _utc_now()
        self.last_eval_monotonic = time.monotonic()
        graph_too_large, graph_metrics = self._graph_pressure()
        memory_dropping, memory_metrics = self._memory_quality_dropping()
        no_new_features = self._no_new_features(recent_feed)
        system_idle = self._system_idle(swarm.agents)
        manual_action = self._consume_manual_command()

        question = "What is best for the system right now?"
        action = manual_action or "maintain"
        if not manual_action:
            if graph_too_large:
                action = "spawn_compression_agents"
            elif memory_dropping:
                action = "spawn_evaluators"
            elif no_new_features:
                action = "spawn_coding_agents"
            elif system_idle:
                action = "allow_research_mode"
        spawned, details = self._apply_action(swarm, action)
        mission_updates = self._assign_boredom_missions(swarm, force=(action == "assign_boredom_missions"))

        evaluation = {
            "time": now.isoformat(),
            "question": question,
            "action": action,
            "details": details,
            "manual_override": bool(manual_action),
            "spawned_agents": spawned,
            "mission_assignments": len(mission_updates),
            "signals": {
                "graph_too_large": graph_too_large,
                "no_new_features": no_new_features,
                "memory_quality_dropping": memory_dropping,
                "system_idle": system_idle,
            },
            "graph_metrics": graph_metrics,
            "memory_metrics": memory_metrics,
        }
        self.history["evaluations"].append(evaluation)
        self._save()

        return [
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "type": "Observation",
                "summary": f"Priority Engine: {question}",
            },
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "type": "Manual Override",
                "summary": (
                    f"Priority Decision -> {action} | {details} | "
                    f"spawned={spawned} | missions={len(mission_updates)} | manual={bool(manual_action)}"
                ),
            },
        ] + mission_updates


# --- Knowledge Graph Interface ---
class AgentKnowledge:
    def __init__(self, uri, user, password, agent_name):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.agent_name = agent_name

    def close(self):
        self.driver.close()

    def add_concept(self, concept, type="Fact"):
        with self.driver.session() as session:
            session.run("MERGE (c:Concept {name:$concept,type:$type})", concept=concept, type=type)

    def add_memory(self, memory, related=[]):
        with self.driver.session() as session:
            session.run(
                "CREATE (m:Memory {agent:$agent,note:$memory, timestamp: datetime()})",
                agent=self.agent_name,
                memory=memory,
            )
            for concept in related:
                session.run(
                    """
                MATCH (m:Memory {note:$memory}), (c:Concept {name:$concept})
                MERGE (m)-[:LinkedTo]->(c)
                """,
                    memory=memory,
                    concept=concept,
                )

    def link_agent_metadata(self, role, traits, skills, tools):
        """Automatically link the agent to their metadata in the KG."""
        with self.driver.session() as session:
            # Create Agent node
            session.run(
                """
                MERGE (a:Agent {name: $name})
                SET a.role = $role, a.traits = $traits
            """,
                name=self.agent_name,
                role=role,
                traits=traits,
            )

            # Link to Role
            session.run(
                """
                MERGE (r:Role {name: $role})
                WITH r
                MATCH (a:Agent {name: $name})
                MERGE (a)-[:PLAYS_ROLE]->(r)
            """,
                name=self.agent_name,
                role=role,
            )

            # Link to Skills
            for skill in skills:
                session.run(
                    """
                    MERGE (s:Skill {name: $skill})
                    WITH s
                    MATCH (a:Agent {name: $name})
                    MERGE (a)-[:HAS_SKILL]->(s)
                """,
                    name=self.agent_name,
                    skill=skill,
                )

            # Link to Tools
            for tool in tools:
                session.run(
                    """
                    MERGE (t:Tool {name: $tool})
                    WITH t
                    MATCH (a:Agent {name: $name})
                    MERGE (a)-[:USES_TOOL]->(t)
                """,
                    name=self.agent_name,
                    tool=tool,
                )


# --- Swarm Agent ---
class SwarmAgent:
    def __init__(self, role, kg_uri, kg_user, kg_password, name_manager):
        self.role = role
        self.name, self.culture = name_manager.get_name(role)
        self.model = MODEL_ASSIGNMENTS.get(self.name, "l3-8b-stheno-v3.2-iq-imatrix")
        self.profile = generate_character_with_llm(self.name, role, self.culture, self.model)
        self.mood = random.choice(MOODS)
        self.kg_uri = kg_uri
        self.kg_user = kg_user
        self.kg_password = kg_password

        # Extracted Metadata
        self.skills = self.profile.get("skills", [])
        self.tools = self.profile.get("tools", [])
        self.personality_type = self.profile.get("personality_type", "Unknown")

        # Fitness metrics
        self.task_success_rate = 0.7
        self.knowledge_contrib = 0
        self.collab_score = 0
        self.trait_synergy = 0
        self.fitness = 0.0
        self.current_mission = None
        self.task_history = []

        # Initial KG linking
        self.register_to_kg()

    def register_to_kg(self):
        try:
            kg = AgentKnowledge(self.kg_uri, self.kg_user, self.kg_password, self.name)
            kg.link_agent_metadata(
                self.role, self.profile.get("personality_traits", []), self.skills, self.tools
            )
            kg.close()
        except Exception as e:
            print(f"KG Registry Error for {self.name}: {e}")

    def select_task(self):
        tasks = ["exploration", "validation", "experiment", "communication"]
        scores = []
        traits = [t.lower() for t in self.profile.get("personality_traits", [])]
        for t in tasks:
            score = 0
            if t == "exploration" and any(x in traits for x in ["curious", "adventurous"]):
                score += 1
            if t == "validation" and any(x in traits for x in ["analytical", "diligent"]):
                score += 1
            if t == "experiment" and any(x in traits for x in ["creative", "visionary"]):
                score += 1
            if t == "communication" and any(x in traits for x in ["social", "loyal"]):
                score += 1
            scores.append((t, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[0][0]

    def perform_task(self):
        mission_task_map = {
            "improve retrieval accuracy": "validation",
            "reduce response latency": "experiment",
            "discover new models": "exploration",
            "optimize memory compression": "validation",
            "design new agents": "experiment",
        }
        mission_hint = mission_task_map.get(str(self.current_mission or "").strip().lower())
        if mission_hint and random.random() < 0.65:
            task_type = mission_hint
        else:
            task_type = self.select_task()
        self.model = pick_task_model(task_type, self.model)
        success = random.random() < 0.75
        concept = f"{self.role} {task_type.capitalize()} Findings {random.randint(100, 999)}"
        memory = f"{self.name} performed '{task_type}' | Status: {'Success' if success else 'Failure'} | Mood: {self.mood}"

        try:
            kg = AgentKnowledge(self.kg_uri, self.kg_user, self.kg_password, self.name)
            kg.add_concept(concept, type="Research")
            kg.add_memory(memory, [concept])
            kg.close()
        except Exception:
            pass  # Silent failure for simulation speed

        # update fitness metrics
        self.task_success_rate = (self.task_success_rate * 9 + (1 if success else 0)) / 10
        self.knowledge_contrib += 1
        self.collab_score += random.uniform(0.1, 0.5) if success else 0

        if success:
            self.mood = random.choice(["Calm", "Excited"])
        else:
            self.mood = random.choice(["Cautious", "Curious"])
        self.task_history.append({"time": _utc_now().isoformat(), "task": task_type, "success": bool(success)})
        self.task_history = self.task_history[-20:]

        return success, memory, concept, task_type


# --- Fitness & Recycling ---
def calculate_fitness(agent):
    fitness = (
        0.4 * agent.task_success_rate
        + 0.3 * (min(agent.knowledge_contrib, 20) / 20)
        + 0.2 * (min(agent.collab_score, 10) / 10)
        + 0.1 * (random.uniform(0.5, 1.0))  # trait synergy simulation
    )
    agent.fitness = round(fitness * 100, 2)
    return fitness


def migrate_to_society(agent, society_uri, user, password):
    """Move retired agent metadata to the Agent_Society graph."""
    print(f"--- Migrating {agent.name} to Agent_Society ---")
    try:
        driver = GraphDatabase.driver(society_uri, auth=(user, password))
        with driver.session() as session:
            session.run(
                """
                MERGE (a:RetiredAgent {name: $name})
                SET a.role = $role,
                    a.culture = $culture,
                    a.personality_type = $personality_type,
                    a.fitness = $fitness,
                    a.skills = $skills,
                    a.tools = $tools,
                    a.traits = $traits,
                    a.backstory = $backstory,
                    a.retirement_date = datetime()
            """,
                name=agent.name,
                role=agent.role,
                culture=agent.culture,
                personality_type=agent.personality_type,
                fitness=agent.fitness,
                skills=agent.skills,
                tools=agent.tools,
                traits=agent.profile.get("personality_traits", []),
                backstory=agent.profile.get("backstory", ""),
            )
        driver.close()
    except Exception as e:
        print(f"Migration error for {agent.name}: {e}")


def recycle_agents(swarm, threshold=10, recycle_percent=0.2):
    if len(swarm.agents) < threshold:
        return

    for agent in swarm.agents:
        calculate_fitness(agent)

    swarm.agents.sort(key=lambda x: x.fitness)

    num_to_recycle = max(1, int(len(swarm.agents) * recycle_percent))
    to_recycle = swarm.agents[:num_to_recycle]

    print(f"\n[SWARM CONTROL] Recycling {num_to_recycle} weakest agents...")
    for agent in to_recycle:
        # Migrate to Agent_Society before removing
        migrate_to_society(agent, SOCIETY_URI, NEO4J_USER, NEO4J_PASSWORD)
        swarm.agents.remove(agent)

    # Re-fill the swarm
    roles_needed = [agent.role for agent in to_recycle]
    for role in roles_needed:
        swarm.add_agent(role)


# --- Raphael Swarm ---
class Raphael_Swarm:
    def __init__(
        self,
        kg_uri=NEO4J_URI,
        kg_user=NEO4J_USER,
        kg_password=NEO4J_PASSWORD,
        recycle_threshold=10,
    ):
        self.agents = []
        self.kg_uri = kg_uri
        self.kg_user = kg_user
        self.kg_password = kg_password
        self.name_manager = NameManager()
        self.swarm_graph = nx.DiGraph() if HAS_VIZ else None
        self.recycle_threshold = recycle_threshold
        self.discovery_pipeline = DiscoveryPipeline(kg_uri, kg_user, kg_password)
        self.priority_engine = SwarmPriorityEngine(kg_uri, kg_user, kg_password)

    def touch_telemetry_heartbeat(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        stats_path = Path(base_dir) / "public" / "stats.json"
        try:
            payload = _read_json(stats_path, {"timestamp": 0, "resources": [], "agents": [], "feed": []})
            if not isinstance(payload, dict):
                payload = {"timestamp": 0, "resources": [], "agents": [], "feed": []}
            payload["timestamp"] = datetime.now().timestamp()
            payload["resources"] = payload.get("resources") if isinstance(payload.get("resources"), list) else []
            payload["agents"] = payload.get("agents") if isinstance(payload.get("agents"), list) else []
            payload["feed"] = payload.get("feed") if isinstance(payload.get("feed"), list) else []
            _atomic_write_json(stats_path, payload)
        except Exception:
            pass

    def add_agent(self, role):
        agent = SwarmAgent(role, self.kg_uri, self.kg_user, self.kg_password, self.name_manager)
        self.agents.append(agent)
        print(f"Agent {agent.name} ({role}, {agent.culture}) initialized.")

    def share_knowledge(self, from_agent_name, concept, memory):
        for agent in self.agents:
            if agent.name != from_agent_name:
                try:
                    kg = AgentKnowledge(self.kg_uri, self.kg_user, self.kg_password, agent.name)
                    kg.add_concept(concept)
                    kg.add_memory(f"Shared Knowledge from {from_agent_name}: {concept}", [concept])
                    kg.close()
                    if self.swarm_graph:
                        self.swarm_graph.add_edge(from_agent_name, agent.name, concept=concept)
                except Exception:
                    pass

    def print_registry(self):
        """Display the agent registry with rankings."""
        print("\n" + "=" * 80)
        print(" AGENT REGISTRY & RANKINGS")
        print("=" * 80)

        # Calculate fitness for all
        for a in self.agents:
            calculate_fitness(a)

        # Global Ranking
        sorted_global = sorted(self.agents, key=lambda x: x.fitness, reverse=True)

        # Role-based Rankings
        role_ranks = {}
        for a in sorted_global:
            if a.role not in role_ranks:
                role_ranks[a.role] = []
            role_ranks[a.role].append(a)

        print(
            f"{'Name':<12} | {'Role':<12} | {'Type':<10} | {'Fit (%)':<8} | {'G-Rank':<6} | {'R-Rank':<6}"
        )
        print("-" * 80)

        for i, agent in enumerate(sorted_global):
            role_rank = role_ranks[agent.role].index(agent) + 1
            print(
                f"{agent.name:<12} | {agent.role:<12} | {agent.personality_type:<10} | {agent.fitness:<8} | {i + 1:<6} | {role_rank:<6}"
            )
        print("=" * 80)

    # --- Statistics Export for Dashboard ---
    def export_stats(self):
        """Export current swarm state to stats.json for the Next.js dashboard."""
        # Fix path to point to the root public directory instead of app/public
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        stats_path = os.path.join(base_dir, "public", "stats.json")
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)

        # Load existing history if running continuously to append to charts
        try:
            with open(stats_path, "r") as f:
                existing_data = json.load(f)
                resources_history = existing_data.get("resources", [])
                feed_history = existing_data.get("feed", [])
        except (FileNotFoundError, json.JSONDecodeError):
            resources_history = []
            feed_history = []

        # Generate mock resource telemetry for the charts
        current_time = datetime.now().strftime("%H:%M:%S")
        new_resource = {
            "name": current_time,
            "cpu": random.randint(20, 85),
            "ram": random.randint(40, 90),
            "vram": random.randint(10, 60),
        }
        resources_history.append(new_resource)
        # Keep last 15 data points for the chart
        if len(resources_history) > 15:
            resources_history = resources_history[-15:]

        # Collect agent data
        reputation_map = _load_reputation().get("agents", {})
        explorers, reviewers, archivists = self.discovery_pipeline._groups(self.agents)
        group_map = {a.name: "Explorer" for a in explorers}
        group_map.update({a.name: "Reviewer" for a in reviewers})
        group_map.update({a.name: "Archivist" for a in archivists})
        priority_eval_count = len(self.priority_engine.history.get("evaluations", []))
        latest_priority = self.priority_engine.history.get("evaluations", [])
        latest_priority_action = latest_priority[-1]["action"] if latest_priority else "none"
        latest_priority_signals = latest_priority[-1].get("signals", {}) if latest_priority else {}
        latest_priority_manual = bool(latest_priority[-1].get("manual_override")) if latest_priority else False
        mission_map = self.priority_engine.get_active_missions()
        agent_data = []
        for a in self.agents:
            agent_data.append(
                {
                    "name": a.name,
                    "role": a.role,
                    "culture": a.culture,
                    "status": "Executing" if a.name in str(feed_history[-3:]) else "Idle",
                    "model": a.model,
                    "fitness": a.fitness,
                    "task_success_rate": round(a.task_success_rate * 100, 1),
                    "knowledge_contrib": a.knowledge_contrib,
                    "reputation": float(reputation_map.get(a.name, 0)),
                    "research_group": group_map.get(a.name, "Explorer"),
                    "priority_action": latest_priority_action,
                    "mission": mission_map.get(a.name),
                }
            )

        # Generate some synthetic feed activity if no recent sharing happened
        if random.random() < 0.3:
            feed_history.append(
                {
                    "time": current_time,
                    "type": "Observation",
                    "summary": f"Swarm telemetry baseline recorded at {current_time}.",
                }
            )

        if len(feed_history) > 20:
            feed_history = feed_history[-20:]

        data = {
            "timestamp": datetime.now().timestamp(),
            "resources": resources_history,
            "agents": agent_data,
            "feed": feed_history,
            "priority_engine": {
                "evaluations": priority_eval_count,
                "latest_action": latest_priority_action,
                "latest_signals": latest_priority_signals,
                "manual_override": latest_priority_manual,
                "active_missions": len(mission_map),
            },
        }

        _atomic_write_json(Path(stats_path), data)

    def run_simulation(self, steps=3, continuous=False):
        import time

        step = 0
        try:
            while True:
                print(f"\n--- Simulation Step {step + 1} ---")
                self.touch_telemetry_heartbeat()

                # If we are exporting stats, load previous feed history
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                stats_path = os.path.join(base_dir, "public", "stats.json")
                feed_updates = []
                exploration_events = []
                explorers, _reviewers, _archivists = self.discovery_pipeline._groups(self.agents)
                explorer_names = {a.name for a in explorers}

                for agent in self.agents:
                    success, memory, concept, task_type = agent.perform_task()
                    self.share_knowledge(agent.name, concept, memory)
                    msg = f"  > {agent.name} ({agent.mood}): {concept} -> Success: {success}"
                    print(msg)

                    feed_updates.append(
                        {
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "type": "Task",
                            "summary": msg.strip(),
                        }
                    )
                    if agent.name in explorer_names:
                        event = self.discovery_pipeline.build_exploration_event(
                            agent=agent,
                            task_type=task_type,
                            concept=concept,
                            success=success,
                        )
                        exploration_events.append(event)
                        feed_updates.append(
                            {
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "type": "Observation",
                                "summary": (
                                    "Exploration Event | "
                                    f"agent={event['agent']} | topic={event['topic']} | "
                                    f"confidence={event['confidence']:.2f} | novelty={event['novelty_estimate']:.2f} | "
                                    f"sources={','.join(event['sources'])}"
                                ),
                            }
                        )

                self.print_registry()
                recycle_agents(self, self.recycle_threshold)

                if exploration_events:
                    feed_updates.extend(self.discovery_pipeline.process_discoveries(self.agents, exploration_events))

                if self.discovery_pipeline.maybe_run_consolidation_cycle():
                    feed_updates.append(
                        {
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "type": "Observation",
                            "summary": "Knowledge Consolidation Cycle completed: merged, summarized, pruned, embeddings refreshed.",
                        }
                    )

                if self.priority_engine.should_run():
                    feed_updates.extend(self.priority_engine.evaluate_and_apply(self, feed_updates))

                # Update feed history and export
                try:
                    with open(stats_path, "r") as f:
                        existing = json.load(f)
                        existing["feed"] = (existing.get("feed", []) + feed_updates)[-20:]
                    _atomic_write_json(Path(stats_path), existing)
                except Exception:
                    pass  # handled in export_stats

                self.export_stats()

                step += 1
                if not continuous and step >= steps:
                    break

                if continuous:
                    print(f"Cycle complete. Cooling down for 5 seconds...")
                    time.sleep(5)

        except KeyboardInterrupt:
            print("\nSwarm simulation gracefully halted.")

    def trigger_agent(self, agent_name):
        """Force an agent to execute a task immediately (e.g., from API)."""
        print(f"--- MANUAL OVERRIDE: TRIGGERING {agent_name} ---")
        agent = next((a for a in self.agents if a.name == agent_name), None)
        if not agent:
            print(f"Agent {agent_name} not found in active swarm.")
            return False

        success, memory, concept, _task_type = agent.perform_task()
        self.share_knowledge(agent.name, concept, memory)
        calculate_fitness(agent)

        # Push to feed
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        stats_path = os.path.join(base_dir, "public", "stats.json")
        try:
            with open(stats_path, "r") as f:
                data = json.load(f)
            data["feed"].append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "Manual Override",
                    "summary": f"USER COMMANDED {agent.name}: {concept} ({'SUCCESS' if success else 'FAILED'})",
                }
            )
            _atomic_write_json(Path(stats_path), data)
        except Exception:
            pass

        self.export_stats()
        return True


# --- Execution ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Raphael Swarm Node")
    parser.add_argument(
        "--continuous", action="store_true", help="Run the swarm indefinitely, updating stats.json"
    )
    parser.add_argument(
        "--trigger", type=str, help="Trigger a specific agent by name to execute a task"
    )
    args = parser.parse_args()

    bootstrap_stats = PROJECT_ROOT / "public" / "stats.json"
    if not bootstrap_stats.exists():
        _atomic_write_json(
            bootstrap_stats,
            {
                "timestamp": datetime.now().timestamp(),
                "resources": [],
                "agents": [],
                "feed": [{"time": datetime.now().strftime("%H:%M:%S"), "type": "Observation", "summary": "Swarm bootstrap started"}],
            },
        )
    else:
        payload = _read_json(bootstrap_stats, {"timestamp": 0, "resources": [], "agents": [], "feed": []})
        if not isinstance(payload, dict):
            payload = {"timestamp": 0, "resources": [], "agents": [], "feed": []}
        payload["timestamp"] = datetime.now().timestamp()
        _atomic_write_json(bootstrap_stats, payload)

    my_swarm = Raphael_Swarm(recycle_threshold=8)

    roles = ["Researcher", "Analyst", "Creative Coder", "Communicator", "Explorer"]
    print("Initializing Swarm...")
    for role in roles:
        my_swarm.add_agent(role)

    my_swarm.export_stats()  # initial output

    if args.trigger:
        my_swarm.trigger_agent(args.trigger)
    else:
        my_swarm.run_simulation(steps=3, continuous=args.continuous)
