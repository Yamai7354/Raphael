import { NextResponse } from "next/server";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
const statsPath = path.join(process.cwd(), "public", "stats.json");
const registryPath = path.join(process.cwd(), "data", "agents.json");

type AgentRecord = {
  name: string;
  role: string;
  culture?: string;
  status?: string;
  model?: string | null;
  fitness?: number;
  task_success_rate?: number;
  knowledge_contrib?: number;
  source?: "registry" | "telemetry";
};

async function readStatsAgents(): Promise<AgentRecord[]> {
  try {
    const raw = await readFile(statsPath, "utf-8");
    const json = JSON.parse(raw) as { agents?: AgentRecord[] };
    return Array.isArray(json.agents) ? json.agents : [];
  } catch {
    return [];
  }
}

async function readRegistryAgents(): Promise<AgentRecord[]> {
  try {
    const raw = await readFile(registryPath, "utf-8");
    const json = JSON.parse(raw) as { agents?: AgentRecord[] };
    return Array.isArray(json.agents) ? json.agents : [];
  } catch {
    return [];
  }
}

async function writeRegistryAgents(agents: AgentRecord[]): Promise<void> {
  await mkdir(path.dirname(registryPath), { recursive: true });
  await writeFile(registryPath, JSON.stringify({ agents }, null, 2), "utf-8");
}

async function readStatsPayload(): Promise<{
  timestamp?: number;
  agents: AgentRecord[];
  resources: unknown[];
  feed: Array<{ time: string; type: string; summary: string }>;
}> {
  try {
    const raw = await readFile(statsPath, "utf-8");
    const json = JSON.parse(raw) as {
      timestamp?: number;
      agents?: AgentRecord[];
      resources?: unknown[];
      feed?: Array<{ time: string; type: string; summary: string }>;
    };
    return {
      timestamp: json.timestamp,
      agents: Array.isArray(json.agents) ? json.agents : [],
      resources: Array.isArray(json.resources) ? json.resources : [],
      feed: Array.isArray(json.feed) ? json.feed : [],
    };
  } catch {
    return { agents: [], resources: [], feed: [] };
  }
}

async function writeStatsPayload(payload: {
  timestamp?: number;
  agents: AgentRecord[];
  resources: unknown[];
  feed: Array<{ time: string; type: string; summary: string }>;
}) {
  await mkdir(path.dirname(statsPath), { recursive: true });
  const tmpPath = `${statsPath}.tmp`;
  await writeFile(
    tmpPath,
    JSON.stringify(
      {
        timestamp: payload.timestamp ?? Date.now() / 1000,
        resources: payload.resources,
        agents: payload.agents,
        feed: payload.feed,
      },
      null,
      2
    ),
    "utf-8"
  );
  await rename(tmpPath, statsPath);
}

async function mergedAgents(): Promise<AgentRecord[]> {
  const [fromStats, fromRegistry] = await Promise.all([readStatsAgents(), readRegistryAgents()]);
  const map = new Map<string, AgentRecord>();

  for (const agent of fromRegistry) {
    map.set(agent.name, { ...agent, source: "registry" });
  }
  for (const agent of fromStats) {
    const existing = map.get(agent.name);
    map.set(agent.name, {
      ...existing,
      ...agent,
      source: "telemetry",
    });
  }

  const merged = [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
  await writeRegistryAgents(merged);
  return merged;
}

export async function GET() {
  const agents = await mergedAgents();
  return NextResponse.json({ agents });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { action?: "start" | "start-all"; agentName?: string };
    const action = body.action ?? "start";

    if (action === "start") {
      if (!body.agentName) {
        return NextResponse.json({ ok: false, error: "agentName is required" }, { status: 400 });
      }
      const payload = await readStatsPayload();
      const now = new Date();
      const time = now.toTimeString().slice(0, 8);
      const updated = payload.agents.map((agent) =>
        agent.name === body.agentName ? { ...agent, status: "Executing" } : agent
      );
      payload.feed.push({
        time,
        type: "Manual Override",
        summary: `USER STARTED ${body.agentName}: execution state set to Executing`,
      });
      await writeStatsPayload({
        ...payload,
        agents: updated,
        feed: payload.feed.slice(-50),
      });
      return NextResponse.json({ ok: true, message: `Started ${body.agentName}` });
    }

    if (action === "start-all") {
      const payload = await readStatsPayload();
      const now = new Date();
      const time = now.toTimeString().slice(0, 8);
      const startedCount = payload.agents.length;
      const updated = payload.agents.map((agent) => ({ ...agent, status: "Executing" }));
      if (startedCount > 0) {
        payload.feed.push({
          time,
          type: "Manual Override",
          summary: `USER STARTED ALL AGENTS: ${startedCount} agent(s) set to Executing`,
        });
      }
      await writeStatsPayload({
        ...payload,
        agents: updated,
        feed: payload.feed.slice(-50),
      });
      return NextResponse.json({ ok: true, message: `Started ${startedCount} agents` });
    }

    return NextResponse.json({ ok: false, error: "Unsupported action" }, { status: 400 });
  } catch (error) {
    console.error("Agent start failed", error);
    return NextResponse.json({ ok: false, error: "Failed to start agent(s)" }, { status: 500 });
  }
}
