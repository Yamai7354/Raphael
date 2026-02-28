import { NextResponse } from "next/server";
import { ensureMemoryRuntime, runMemoryAction } from "@/lib/memory-system";

export async function GET() {
  const runtime = await ensureMemoryRuntime();
  if (!runtime.ok) {
    return NextResponse.json({ ok: false, error: "Runtime missing", detail: runtime.detail }, { status: 500 });
  }

  try {
    const parsed = await runMemoryAction("health");
    return NextResponse.json(parsed, { status: parsed.ok ? 200 : 500 });
  } catch (error) {
    console.error("Memory health failed", error);
    return NextResponse.json({ ok: false, error: "Memory health failed" }, { status: 500 });
  }
}
