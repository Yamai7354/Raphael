import { NextResponse } from "next/server";
import { ensureMemoryRuntime, runMemoryAction } from "@/lib/memory-system";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const runtime = await ensureMemoryRuntime();
  if (!runtime.ok) {
    return NextResponse.json({ ok: false, error: "Runtime missing", detail: runtime.detail }, { status: 500 });
  }

  try {
    const parsed = await runMemoryAction("write", body);
    return NextResponse.json(parsed, { status: parsed.ok ? 200 : 400 });
  } catch (error) {
    console.error("Memory write failed", error);
    return NextResponse.json({ ok: false, error: "Memory write failed" }, { status: 500 });
  }
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const runtime = await ensureMemoryRuntime();
  if (!runtime.ok) {
    return NextResponse.json({ ok: false, error: "Runtime missing", detail: runtime.detail }, { status: 500 });
  }

  const payload: Record<string, unknown> = {
    q: url.searchParams.get("q") ?? "",
    memory_type: url.searchParams.get("type") ?? "",
    k: Number(url.searchParams.get("k") ?? "10"),
  };

  try {
    const parsed = await runMemoryAction("query", payload);
    return NextResponse.json(parsed, { status: parsed.ok ? 200 : 400 });
  } catch (error) {
    console.error("Memory query failed", error);
    return NextResponse.json({ ok: false, error: "Memory query failed" }, { status: 500 });
  }
}
