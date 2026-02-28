import { NextResponse } from "next/server";
import { access, readFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const pythonPath = path.join(process.cwd(), ".venv", "bin", "python");
const scriptPath = path.join(process.cwd(), "app", "hybridize_research_graph.py");
const reportPath = path.join(process.cwd(), "data", "research_hybrid_report.json");

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
  const body = (await request.json().catch(() => ({}))) as {
    limit?: number;
    embed?: boolean;
    embedModel?: string;
    prune?: boolean;
    pruneDays?: number;
    pruneBatch?: number;
    compact?: boolean;
    aggressivePrune?: boolean;
  };

  try {
    await access(pythonPath);
    await access(scriptPath);
  } catch {
    return NextResponse.json(
      { ok: false, error: "Runtime missing", detail: `Need ${pythonPath} and ${scriptPath}` },
      { status: 500 }
    );
  }

  const args = [scriptPath, "--limit", String(Math.max(10, Math.min(25000, Number(body.limit ?? 4000))))];
  if (body.embed) {
    args.push("--embed");
    if (body.embedModel) args.push("--embed-model", body.embedModel.slice(0, 80));
  }
  if (body.prune) {
    args.push("--prune");
    args.push("--prune-days", String(Math.max(1, Math.min(3650, Number(body.pruneDays ?? 14)))));
    args.push("--prune-batch", String(Math.max(100, Math.min(50000, Number(body.pruneBatch ?? 5000)))));
    if (body.aggressivePrune) {
      args.push("--aggressive-prune");
    }
  }
  if (body.compact) {
    args.push("--compact");
  }

  try {
    const { stdout } = await execFileAsync(pythonPath, args, {
      timeout: 600_000,
      maxBuffer: 10 * 1024 * 1024,
    });
    const parsed = JSON.parse(stdout) as Record<string, unknown>;
    return NextResponse.json({ ok: true, report: parsed });
  } catch (error) {
    console.error("Hybrid research migration failed", error);
    return NextResponse.json({ ok: false, error: "Hybrid migration failed" }, { status: 500 });
  }
}
