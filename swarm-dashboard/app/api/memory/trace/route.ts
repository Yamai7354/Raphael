import { NextResponse } from "next/server";
import { ensureMemoryRuntime, runMemoryAction } from "@/lib/memory-system";

export async function GET(request: Request) {
  const runtime = await ensureMemoryRuntime();
  if (!runtime.ok) {
    return NextResponse.json({ ok: false, error: "Runtime missing", detail: runtime.detail }, { status: 500 });
  }

  const url = new URL(request.url);
  const windowDays = Math.max(1, Math.min(30, Number(url.searchParams.get("windowDays") ?? "1")));

  try {
    const parsed = await runMemoryAction("trace", { window_days: windowDays });
    return NextResponse.json(parsed, { status: parsed.ok ? 200 : 500 });
  } catch (error) {
    console.error("Memory trace failed", error);
    return NextResponse.json({ ok: false, error: "Memory trace failed" }, { status: 500 });
  }
}
