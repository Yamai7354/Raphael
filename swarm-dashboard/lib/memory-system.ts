import { access } from "node:fs/promises";
import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const pythonPath = path.join(process.cwd(), ".venv", "bin", "python");
const scriptPath = path.join(process.cwd(), "app", "memory_system.py");

function toPayloadB64(payload: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(payload), "utf-8").toString("base64");
}

export async function ensureMemoryRuntime(): Promise<{ ok: true } | { ok: false; detail: string }> {
  try {
    await access(pythonPath);
    await access(scriptPath);
    return { ok: true };
  } catch {
    return {
      ok: false,
      detail: `Need ${pythonPath} and ${scriptPath}`,
    };
  }
}

export async function runMemoryAction(
  action: "write" | "query" | "health" | "consolidate" | "retention" | "conflicts" | "trace",
  payload: Record<string, unknown> = {}
) {
  const args = [scriptPath, "--action", action, "--payload-b64", toPayloadB64(payload)];
  const { stdout } = await execFileAsync(pythonPath, args, {
    timeout: 300_000,
    maxBuffer: 10 * 1024 * 1024,
  });
  return JSON.parse(stdout) as Record<string, unknown>;
}
