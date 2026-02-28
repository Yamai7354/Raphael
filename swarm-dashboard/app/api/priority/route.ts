import { NextResponse } from "next/server";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

type PriorityAction =
  | "spawn_compression_agents"
  | "spawn_evaluators"
  | "spawn_coding_agents"
  | "allow_research_mode"
  | "assign_boredom_missions"
  | "maintain";

type PriorityEvaluation = {
  time?: string;
  question?: string;
  action?: PriorityAction | string;
  details?: string;
  manual_override?: boolean;
  spawned_agents?: number;
  mission_assignments?: number;
  signals?: Record<string, boolean>;
  graph_metrics?: Record<string, number | null>;
  memory_metrics?: Record<string, number | null>;
};

type MissionState = {
  agents?: Record<string, { mission?: string; assigned_at?: string; reason?: string }>;
  history?: Array<{ agent?: string; mission?: string; assigned_at?: string; reason?: string }>;
};

const dataDir = path.join(process.cwd(), "data");
const priorityStatePath = path.join(dataDir, "swarm_priority_state.json");
const priorityCommandPath = path.join(dataDir, "swarm_priority_command.json");
const agentMissionsPath = path.join(dataDir, "agent_missions.json");

const allowedActions: PriorityAction[] = [
  "spawn_compression_agents",
  "spawn_evaluators",
  "spawn_coding_agents",
  "allow_research_mode",
  "assign_boredom_missions",
  "maintain",
];

async function readJsonSafe<T>(filePath: string, fallback: T): Promise<T> {
  try {
    const raw = await readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

async function writeJsonAtomic(filePath: string, payload: unknown): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true });
  const tmpPath = `${filePath}.tmp`;
  await writeFile(tmpPath, JSON.stringify(payload, null, 2), "utf-8");
  await rename(tmpPath, filePath);
}

export async function GET() {
  const state = await readJsonSafe<{ evaluations?: PriorityEvaluation[] }>(priorityStatePath, { evaluations: [] });
  const evaluations = Array.isArray(state.evaluations) ? state.evaluations : [];
  const latest = evaluations.length > 0 ? evaluations[evaluations.length - 1] : null;

  const missions = await readJsonSafe<MissionState>(agentMissionsPath, { agents: {}, history: [] });
  const missionAgents = missions.agents && typeof missions.agents === "object" ? missions.agents : {};
  const missionEntries = Object.entries(missionAgents)
    .map(([agent, payload]) => ({
      agent,
      mission: payload?.mission ?? "",
      assignedAt: payload?.assigned_at ?? null,
      reason: payload?.reason ?? null,
    }))
    .filter((entry) => entry.mission.length > 0)
    .sort((a, b) => a.agent.localeCompare(b.agent));

  return NextResponse.json({
    ok: true,
    actions: allowedActions,
    evaluationsCount: evaluations.length,
    latestEvaluation: latest,
    activeMissions: missionEntries,
    missionCount: missionEntries.length,
  });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as { action?: PriorityAction };
    const action = body.action;

    if (!action || !allowedActions.includes(action)) {
      return NextResponse.json({ ok: false, error: "Unsupported action" }, { status: 400 });
    }

    await writeJsonAtomic(priorityCommandPath, {
      action,
      requested_at: new Date().toISOString(),
      source: "dashboard",
    });

    return NextResponse.json({ ok: true, message: `Queued priority action: ${action}` });
  } catch (error) {
    console.error("priority action failed", error);
    return NextResponse.json({ ok: false, error: "Failed to queue priority action" }, { status: 500 });
  }
}
