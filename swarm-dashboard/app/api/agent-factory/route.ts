import { NextResponse } from "next/server";
import { access, readFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const pythonPath = path.join(process.cwd(), ".venv", "bin", "python");
const scriptPath = path.join(process.cwd(), "app", "agent_factory_builder.py");
const reportPath = path.join(process.cwd(), "data", "agent_factory_report.json");

async function readReport() {
  try {
    const raw = await readFile(reportPath, "utf-8");
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function GET() {
  const report = await readReport();
  return NextResponse.json({ ok: true, report });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { goal?: string };
  const goal = (body.goal ?? "").trim();

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
    const args = [scriptPath];
    if (goal.length > 0) {
      args.push("--goal", goal.slice(0, 240));
    }

    const { stdout } = await execFileAsync(pythonPath, args, {
      timeout: 180_000,
      maxBuffer: 3 * 1024 * 1024,
    });
    const parsed = JSON.parse(stdout) as { ok?: boolean; report?: unknown };
    return NextResponse.json({ ok: parsed.ok ?? true, report: parsed.report ?? null });
  } catch (error) {
    console.error("Agent factory failed", error);
    return NextResponse.json({ ok: false, error: "Failed to run agent factory" }, { status: 500 });
  }
}
