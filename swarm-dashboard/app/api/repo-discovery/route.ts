import { NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { access } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const pythonPath = path.join(process.cwd(), ".venv", "bin", "python");
const scriptPath = path.join(process.cwd(), "app", "repo_discovery_agent.py");
const workspaceRoot = path.resolve(process.cwd(), "..");

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const entity = searchParams.get("entity") ?? "all";
  const term = searchParams.get("term");
  const rawLimit = Number.parseInt(searchParams.get("limit") ?? "300", 10);
  const limit = Number.isFinite(rawLimit) ? String(Math.min(Math.max(rawLimit, 1), 2000)) : "300";

  if (!["all", "agent", "skill", "tool"].includes(entity)) {
    return NextResponse.json({ ok: false, error: "entity must be all|agent|skill|tool" }, { status: 400 });
  }

  try {
    await access(pythonPath);
    await access(scriptPath);
  } catch {
    return NextResponse.json(
      { ok: false, error: "Runtime missing", detail: `Need ${pythonPath} and ${scriptPath}` },
      { status: 500 }
    );
  }

  try {
    const args = [scriptPath, "--root", workspaceRoot, "--entity", entity, "--limit", limit];
    if (term) {
      args.push("--term", term);
    }

    const { stdout } = await execFileAsync(pythonPath, args, { timeout: 120_000 });
    const payload = JSON.parse(stdout);
    return NextResponse.json({ ok: true, ...payload });
  } catch (error) {
    console.error("Repo discovery failed", error);
    return NextResponse.json({ ok: false, error: "Failed to run repo discovery agent" }, { status: 500 });
  }
}
