import { NextResponse } from "next/server";
import { ensureMemoryRuntime, runMemoryAction } from "@/lib/memory-system";

type MaintenanceBody = {
  actions?: Array<"consolidate" | "retention" | "conflicts">;
  payload?: Record<string, unknown>;
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as MaintenanceBody;
  const runtime = await ensureMemoryRuntime();
  if (!runtime.ok) {
    return NextResponse.json({ ok: false, error: "Runtime missing", detail: runtime.detail }, { status: 500 });
  }

  const actions = Array.isArray(body.actions) && body.actions.length > 0 ? body.actions : ["consolidate", "retention", "conflicts"];
  const payload = body.payload ?? {};

  try {
    const results: Record<string, unknown> = {};
    for (const action of actions) {
      results[action] = await runMemoryAction(action, payload);
    }
    return NextResponse.json({ ok: true, results });
  } catch (error) {
    console.error("Memory maintenance failed", error);
    return NextResponse.json({ ok: false, error: "Memory maintenance failed" }, { status: 500 });
  }
}
