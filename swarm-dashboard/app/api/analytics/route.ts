import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

type Agent = {
  name: string;
  status?: string;
  fitness?: number;
};

type StatsPayload = {
  timestamp?: number;
  agents?: Agent[];
  feed?: Array<{ type?: string }>;
  resources?: Array<{ cpu?: number; ram?: number; vram?: number }>;
};

async function readStats(): Promise<StatsPayload> {
  try {
    const statsPath = path.join(process.cwd(), "public", "stats.json");
    const raw = await readFile(statsPath, "utf-8");
    return JSON.parse(raw) as StatsPayload;
  } catch {
    return {};
  }
}

export async function GET() {
  const stats = await readStats();
  const agents = Array.isArray(stats.agents) ? stats.agents : [];
  const feed = Array.isArray(stats.feed) ? stats.feed : [];
  const resources = Array.isArray(stats.resources) ? stats.resources : [];

  const totalAgents = agents.length;
  const activeAgents = agents.filter((agent) => agent.status === "Executing").length;
  const averageFitness =
    totalAgents === 0
      ? 0
      : Number(
          (
            agents.reduce((sum, agent) => sum + (typeof agent.fitness === "number" ? agent.fitness : 0), 0) /
            totalAgents
          ).toFixed(1)
        );
  const manualOverrides = feed.filter((item) => item.type === "Manual Override").length;
  const lastResource = resources.at(-1) ?? {};

  return NextResponse.json({
    timestamp: stats.timestamp ?? Date.now() / 1000,
    metrics: {
      totalAgents,
      activeAgents,
      idleAgents: Math.max(0, totalAgents - activeAgents),
      averageFitness,
      manualOverrides,
      cpu: typeof lastResource.cpu === "number" ? lastResource.cpu : 0,
      ram: typeof lastResource.ram === "number" ? lastResource.ram : 0,
      vram: typeof lastResource.vram === "number" ? lastResource.vram : 0,
    },
  });
}
