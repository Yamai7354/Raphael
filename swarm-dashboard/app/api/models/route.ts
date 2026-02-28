import { NextResponse } from "next/server";
import { access, readFile } from "node:fs/promises";
import { execFile, execSync } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const pythonPath = path.join(process.cwd(), ".venv", "bin", "python");
const syncScriptPath = path.join(process.cwd(), "app", "sync_ollama_models.py");
const reportPath = path.join(process.cwd(), "data", "model_sync_report.json");

function listModels(): string[] {
  try {
    const raw = execSync("ollama list", { encoding: "utf-8" });
    const lines = raw.split("\n").map((line) => line.trim()).filter(Boolean);
    if (lines.length <= 1) return [];
    return [...new Set(lines.slice(1).map((line) => line.split(/\s+/)[0]).filter(Boolean))];
  } catch {
    return [];
  }
}

async function readReport() {
  try {
    const raw = await readFile(reportPath, "utf-8");
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function GET() {
  const models = listModels();
  const report = await readReport();
  return NextResponse.json({ ok: true, models, report });
}

export async function POST() {
  try {
    await access(pythonPath);
    await access(syncScriptPath);
  } catch {
    return NextResponse.json({ ok: false, error: "Runtime missing for model sync" }, { status: 500 });
  }

  try {
    const { stdout } = await execFileAsync(pythonPath, [syncScriptPath], {
      timeout: 240_000,
      maxBuffer: 5 * 1024 * 1024,
    });
    const payload = JSON.parse(stdout) as Record<string, unknown>;
    return NextResponse.json({ ok: true, ...payload });
  } catch (error) {
    console.error("Model sync failed", error);
    return NextResponse.json({ ok: false, error: "Model sync failed" }, { status: 500 });
  }
}
