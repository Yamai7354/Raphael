import { NextResponse } from "next/server";
import { mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { createDefaultSettings } from "@/lib/settings-schema";

const pidPath = path.join(process.cwd(), "data", "swarm.pid");
const statsPath = path.join(process.cwd(), "public", "stats.json");
const settingsPath = path.join(process.cwd(), "data", "settings.json");
const registryPath = path.join(process.cwd(), "data", "agents.json");
const pythonPath = path.join(process.cwd(), ".venv", "bin", "python");
const scriptPath = path.join(process.cwd(), "app", "agent_recycling_swarm.py");

function isRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function readPid(): Promise<number | null> {
  try {
    const raw = await readFile(pidPath, "utf-8");
    const pid = Number(raw.trim());
    return Number.isFinite(pid) ? pid : null;
  } catch {
    return null;
  }
}

async function swarmStatus() {
  const pid = await readPid();
  const up = pid !== null && isRunning(pid);
  if (!up && pid !== null) {
    await rm(pidPath, { force: true });
  }
  return { up, detail: up ? "Worker loop running" : "Worker loop offline" };
}

async function telemetryStatus() {
  try {
    const info = await stat(statsPath);
    const ageMs = Date.now() - info.mtimeMs;
    if (ageMs < 5 * 60_000) {
      return { up: true, detail: "Telemetry fresh" };
    }
    if (ageMs < 15 * 60_000) {
      return { up: true, detail: "Telemetry delayed" };
    }
    return { up: false, detail: "Telemetry stale" };
  } catch {
    return { up: false, detail: "stats.json missing" };
  }
}

async function settingsStatus() {
  try {
    const raw = await readFile(settingsPath, "utf-8");
    JSON.parse(raw);
    return { up: true, detail: "Settings store reachable" };
  } catch {
    return { up: false, detail: "Settings store unavailable" };
  }
}

async function registryStatus() {
  try {
    const raw = await readFile(registryPath, "utf-8");
    const json = JSON.parse(raw) as { agents?: unknown[] };
    const count = Array.isArray(json.agents) ? json.agents.length : 0;
    return { up: count > 0, detail: count > 0 ? `${count} agents indexed` : "Registry empty" };
  } catch {
    return { up: false, detail: "Registry unavailable" };
  }
}

async function statusSnapshot() {
  const [swarm, telemetry, settings, registry] = await Promise.all([
    swarmStatus(),
    telemetryStatus(),
    settingsStatus(),
    registryStatus(),
  ]);

  return [
    { id: "swarm", name: "Swarm Engine", ...swarm },
    { id: "telemetry", name: "Telemetry Stream", ...telemetry },
    { id: "settings", name: "Settings Store", ...settings },
    { id: "registry", name: "Agent Registry", ...registry },
  ];
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function resetComponent(componentId: string) {
  if (componentId === "swarm") {
    const pid = await readPid();
    if (pid === null || !isRunning(pid)) {
      await mkdir(path.dirname(pidPath), { recursive: true });
      const child = spawn(pythonPath, [scriptPath, "--continuous"], {
        detached: true,
        stdio: "ignore",
      });
      child.unref();
      await writeFile(pidPath, String(child.pid), "utf-8");
    }
    return;
  }

  if (componentId === "telemetry") {
    await mkdir(path.dirname(statsPath), { recursive: true });
    let existing: unknown = null;
    try {
      existing = JSON.parse(await readFile(statsPath, "utf-8"));
    } catch {
      existing = { agents: [], resources: [], feed: [] };
    }
    const safe = existing && typeof existing === "object" ? (existing as Record<string, unknown>) : {};
    safe.timestamp = Date.now() / 1000;
    await writeFile(statsPath, JSON.stringify(safe, null, 2), "utf-8");
    return;
  }

  if (componentId === "settings") {
    await mkdir(path.dirname(settingsPath), { recursive: true });
    await writeFile(settingsPath, JSON.stringify(createDefaultSettings(), null, 2), "utf-8");
    return;
  }

  if (componentId === "registry") {
    await mkdir(path.dirname(registryPath), { recursive: true });
    let agents: unknown[] = [];
    try {
      const stats = JSON.parse(await readFile(statsPath, "utf-8")) as { agents?: unknown[] };
      agents = Array.isArray(stats.agents) ? stats.agents : [];
    } catch {
      agents = [];
    }
    await writeFile(registryPath, JSON.stringify({ agents }, null, 2), "utf-8");
  }
}

export async function GET() {
  const components = await statusSnapshot();
  return NextResponse.json({ components });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { componentId?: string };
  if (!body.componentId) {
    return NextResponse.json({ ok: false, error: "componentId required" }, { status: 400 });
  }

  await sleep(1200);
  await resetComponent(body.componentId);
  const components = await statusSnapshot();
  return NextResponse.json({ ok: true, components });
}
