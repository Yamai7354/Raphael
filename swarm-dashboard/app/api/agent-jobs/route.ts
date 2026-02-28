import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

type Agent = {
  name: string;
  role: string;
  status?: string;
  fitness?: number;
};

type FeedItem = {
  time?: string;
  summary?: string;
  type?: string;
};

async function readStats(): Promise<{ agents: Agent[]; feed: FeedItem[] }> {
  try {
    const statsPath = path.join(process.cwd(), "public", "stats.json");
    const raw = await readFile(statsPath, "utf-8");
    const json = JSON.parse(raw) as { agents?: Agent[]; feed?: FeedItem[] };
    return {
      agents: Array.isArray(json.agents) ? json.agents : [],
      feed: Array.isArray(json.feed) ? json.feed : [],
    };
  } catch {
    return { agents: [], feed: [] };
  }
}

export async function GET() {
  const { agents, feed } = await readStats();
  const active = agents.filter((agent) => agent.status === "Executing");
  const source = active.length > 0 ? active : agents;

  const jobs = source.map((agent) => {
    const latest = [...feed].reverse().find((item) => (item.summary ?? "").includes(agent.name));
    const currentJob = latest?.summary ?? `${agent.role} telemetry synchronization`;
    const status = latest?.type ?? agent.status ?? "Idle";
    const base = typeof agent.fitness === "number" ? agent.fitness : 30;
    const projection = Array.from({ length: 8 }).map((_, idx) => ({
      step: idx + 1,
      projectedFitness: Number((base + idx * 1.4 + Math.max(0, (Math.random() - 0.5) * 3)).toFixed(1)),
    }));

    return {
      name: agent.name,
      role: agent.role,
      status,
      currentJob,
      projection,
      updatedAt: latest?.time ?? null,
    };
  });

  return NextResponse.json({
    jobs,
    activeCount: active.length,
  });
}
