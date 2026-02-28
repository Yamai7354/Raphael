import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { access, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const pidPath = path.join(process.cwd(), "data", "swarm.pid");
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
    if (!Number.isFinite(pid)) return null;
    return pid;
  } catch {
    return null;
  }
}

async function getStatus() {
  const pid = await readPid();
  const running = pid !== null && isRunning(pid);
  if (!running && pid !== null) {
    await rm(pidPath, { force: true });
  }
  return { running, pid: running ? pid : null };
}

export async function GET() {
  const status = await getStatus();
  return NextResponse.json(status);
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { action?: "start" | "stop" };
  const action = body.action ?? "start";

  if (action === "start") {
    const status = await getStatus();
    if (status.running) {
      return NextResponse.json({ ok: true, ...status, message: "Swarm already running" });
    }

    try {
      await access(pythonPath);
      await access(scriptPath);
    } catch {
      return NextResponse.json(
        {
          ok: false,
          error: "Runtime missing",
          detail: `Expected python at ${pythonPath} and script at ${scriptPath}`,
        },
        { status: 500 }
      );
    }

    await mkdir(path.dirname(pidPath), { recursive: true });
    const child = spawn(pythonPath, [scriptPath, "--continuous"], {
      detached: true,
      stdio: "ignore",
    });
    child.unref();
    await writeFile(pidPath, String(child.pid), "utf-8");
    return NextResponse.json({ ok: true, running: true, pid: child.pid, message: "Swarm started" });
  }

  if (action === "stop") {
    const pid = await readPid();
    if (pid !== null && isRunning(pid)) {
      try {
        process.kill(pid, "SIGTERM");
      } catch {
        // ignore kill race
      }
    }
    await rm(pidPath, { force: true });
    return NextResponse.json({ ok: true, running: false, pid: null, message: "Swarm stopped" });
  }

  return NextResponse.json({ ok: false, error: "Unsupported action" }, { status: 400 });
}
