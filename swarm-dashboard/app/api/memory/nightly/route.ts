import { NextResponse } from "next/server";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { ensureMemoryRuntime, runMemoryAction } from "@/lib/memory-system";

type NightlyRun = {
  ranAt: string;
  result: Record<string, unknown>;
};

type NightlyHistory = {
  runs: NightlyRun[];
};

const historyPath = path.join(process.cwd(), "data", "memory-maintenance-history.json");

async function readHistory(): Promise<NightlyHistory> {
  try {
    const raw = await readFile(historyPath, "utf-8");
    const parsed = JSON.parse(raw) as NightlyHistory;
    return { runs: Array.isArray(parsed.runs) ? parsed.runs : [] };
  } catch {
    return { runs: [] };
  }
}

async function writeHistory(payload: NightlyHistory): Promise<void> {
  await mkdir(path.dirname(historyPath), { recursive: true });
  await writeFile(historyPath, JSON.stringify(payload, null, 2), "utf-8");
}

export async function GET() {
  const history = await readHistory();
  return NextResponse.json({ ok: true, history });
}

export async function POST(request: Request) {
  const runtime = await ensureMemoryRuntime();
  if (!runtime.ok) {
    return NextResponse.json({ ok: false, error: "Runtime missing", detail: runtime.detail }, { status: 500 });
  }

  const body = (await request.json().catch(() => ({}))) as {
    force?: boolean;
    payload?: Record<string, unknown>;
  };

  const history = await readHistory();
  const now = new Date();
  const lastRun = history.runs[history.runs.length - 1];
  const lastTs = lastRun ? Date.parse(lastRun.ranAt) : Number.NaN;
  const tooSoon = Number.isFinite(lastTs) && now.getTime() - lastTs < 20 * 60 * 60 * 1000;

  if (tooSoon && !body.force) {
    return NextResponse.json({ ok: true, skipped: true, reason: "Recent run exists", lastRun: lastRun?.ranAt ?? null });
  }

  const payload = body.payload ?? {
    window_days: 7,
    min_items: 6,
    keep_days: 90,
    confidence_threshold: 0.35,
    limit: 10000,
  };

  try {
    const result = {
      consolidate: await runMemoryAction("consolidate", payload),
      retention: await runMemoryAction("retention", payload),
      conflicts: await runMemoryAction("conflicts", payload),
      trace: await runMemoryAction("trace", { window_days: 1 }),
      health: await runMemoryAction("health"),
    };

    history.runs.push({ ranAt: now.toISOString(), result });
    history.runs = history.runs.slice(-30);
    await writeHistory(history);

    return NextResponse.json({ ok: true, ranAt: now.toISOString(), result });
  } catch (error) {
    console.error("Nightly memory maintenance failed", error);
    return NextResponse.json({ ok: false, error: "Nightly memory maintenance failed" }, { status: 500 });
  }
}
