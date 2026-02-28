import { NextResponse } from "next/server";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import {
  buildActivityByAgent,
  buildVerificationResponse,
  extractMentionedAgents,
  ingestStatsFeedToHistory,
  readStatsPayload,
} from "@/lib/agent-activity";
import { ensureMemoryRuntime, runMemoryAction } from "@/lib/memory-system";

type BoardType = "verification" | "idea";

type BoardResponse = {
  id?: string;
  responder: string;
  message: string;
  createdAt: string;
  feedback?: {
    useful: number;
    notUseful: number;
  };
};

type BoardItem = {
  id: string;
  type: BoardType;
  author: string;
  message: string;
  createdAt: string;
  requiredResponders?: string[];
  responses?: BoardResponse[];
  researchContext?: MemoryContextHit[];
  slaMinutes?: number;
  escalatedAt?: string;
};

type BoardPayload = {
  items: BoardItem[];
};

type MemoryContextHit = {
  id: string;
  sourceAgent: string;
  summary: string;
  memoryType: string;
  score: number;
  confidence: number;
  createdAt: string;
};

const boardPath = path.join(process.cwd(), "data", "collab-board.json");
const DEFAULT_SLA_MINUTES = 10;
const ESCALATION_COOLDOWN_MINUTES = 10;
const ESCALATION_BATCH = 2;
const ESCALATION_MAX_RESPONDERS = 12;

async function readBoard(): Promise<BoardPayload> {
  try {
    const raw = await readFile(boardPath, "utf-8");
    const parsed = JSON.parse(raw) as BoardPayload;
    return { items: Array.isArray(parsed.items) ? parsed.items : [] };
  } catch {
    return { items: [] };
  }
}

async function writeBoard(payload: BoardPayload): Promise<void> {
  await mkdir(path.dirname(boardPath), { recursive: true });
  await writeFile(boardPath, JSON.stringify(payload, null, 2), "utf-8");
}

function isBoardType(value: string): value is BoardType {
  return value === "verification" || value === "idea";
}

function pendingResponders(item: BoardItem): string[] {
  const required = item.requiredResponders ?? [];
  const answered = new Set((item.responses ?? []).map((response) => response.responder));
  return required.filter((name) => !answered.has(name));
}

async function lookupMemoryContext(query: string, responders: string[]): Promise<MemoryContextHit[]> {
  const runtime = await ensureMemoryRuntime();
  if (!runtime.ok) return [];

  try {
    const parsed = await runMemoryAction("query", { q: query, k: 12 });
    const items = Array.isArray(parsed.items) ? parsed.items : [];
    const normalizedResponders = new Set(responders.map((name) => name.trim().toLowerCase()).filter(Boolean));

    const filtered = items
      .map((item) => {
        const row = item as Record<string, unknown>;
        return {
          id: String(row.id ?? ""),
          sourceAgent: String(row.source_agent ?? "Unknown"),
          summary: String(row.summary ?? row.content ?? "").trim(),
          memoryType: String(row.memory_type ?? "unknown"),
          score: Number(row.score ?? 0),
          confidence: Number(row.confidence ?? 0),
          createdAt: String(row.created_at ?? ""),
        };
      })
      .filter((hit) => hit.id && hit.summary);

    const prioritized = filtered.filter((hit) => normalizedResponders.has(hit.sourceAgent.trim().toLowerCase()));
    const pool = prioritized.length > 0 ? prioritized : filtered;
    return pool.slice(0, 4);
  } catch {
    return [];
  }
}

function withContextMessage(base: string, responder: string, context: MemoryContextHit[]): string {
  const match = context.find((hit) => hit.sourceAgent.trim().toLowerCase() === responder.trim().toLowerCase()) ?? context[0];
  if (!match) return base;
  const confidencePct = Math.round(Math.max(0, Math.min(1, match.confidence || 0)) * 100);
  const provenance = match.createdAt ? ` @ ${new Date(match.createdAt).toLocaleString()}` : "";
  return `${base} Context: ${match.sourceAgent} logged ${match.memoryType} memory (${confidencePct}% confidence${provenance}) -> ${match.summary.slice(0, 180)}`;
}

function topResponderBackups(activity: Record<string, ReturnType<typeof buildActivityByAgent>[string]>, exclude: string[]): string[] {
  const banned = new Set(exclude.map((name) => name.trim().toLowerCase()));
  return Object.values(activity)
    .sort((a, b) => {
      if (b.successRate !== a.successRate) return b.successRate - a.successRate;
      return b.jobsCompleted - a.jobsCompleted;
    })
    .map((a) => a.name.trim())
    .filter((name) => name && !banned.has(name.toLowerCase()));
}

async function responderPlan(message: string): Promise<{ required: string[]; activity: Record<string, ReturnType<typeof buildActivityByAgent>[string]> }> {
  const stats = await readStatsPayload();
  const history = await ingestStatsFeedToHistory(stats);
  const activity = buildActivityByAgent(stats, history);
  const names = Object.keys(activity);
  const mentioned = extractMentionedAgents(message, names);

  if (mentioned.length > 0) {
    return { required: mentioned, activity };
  }

  const executing = stats.agents
    .filter((agent) => (agent.status ?? "").toLowerCase() === "executing")
    .map((agent) => agent.name.trim())
    .filter(Boolean);

  const fallback = (executing.length > 0 ? executing : names).slice(0, 8);
  return { required: [...new Set(fallback)], activity };
}

export async function GET() {
  const payload = await readBoard();
  const stats = await readStatsPayload();
  const history = await ingestStatsFeedToHistory(stats);
  const activity = buildActivityByAgent(stats, history);
  const now = Date.now();
  let changed = false;

  payload.items = payload.items.map((raw) => {
    const item: BoardItem = {
      ...raw,
      responses: Array.isArray(raw.responses) ? raw.responses : [],
      requiredResponders: Array.isArray(raw.requiredResponders) ? raw.requiredResponders : [],
      researchContext: Array.isArray(raw.researchContext) ? raw.researchContext : [],
      slaMinutes: typeof raw.slaMinutes === "number" ? raw.slaMinutes : DEFAULT_SLA_MINUTES,
      escalatedAt: typeof raw.escalatedAt === "string" ? raw.escalatedAt : undefined,
    };

    if (item.type !== "verification") return item;

    const pending = pendingResponders(item);
    if (pending.length === 0) return item;

    const createdTs = Date.parse(item.createdAt);
    const ageMinutes = Number.isFinite(createdTs) ? Math.floor((now - createdTs) / 60_000) : 0;
    const isStale = ageMinutes >= (item.slaMinutes ?? DEFAULT_SLA_MINUTES);
    if (!isStale) return item;

    const lastEscalatedTs = item.escalatedAt ? Date.parse(item.escalatedAt) : Number.NaN;
    const canEscalateAgain =
      !Number.isFinite(lastEscalatedTs) || now - lastEscalatedTs >= ESCALATION_COOLDOWN_MINUTES * 60_000;

    if (!canEscalateAgain || (item.requiredResponders?.length ?? 0) >= ESCALATION_MAX_RESPONDERS) {
      return item;
    }

    const backups = topResponderBackups(activity, item.requiredResponders ?? []).slice(0, ESCALATION_BATCH);
    if (backups.length === 0) return item;

    item.requiredResponders = [...(item.requiredResponders ?? []), ...backups];
    item.escalatedAt = new Date(now).toISOString();
    item.responses = [
      ...(item.responses ?? []),
      {
        responder: "System Escalation",
        message: `SLA exceeded (${ageMinutes}m). Escalated to: ${backups.join(", ")}.`,
        createdAt: item.escalatedAt,
      },
    ];
    changed = true;
    return item;
  });

  if (changed) {
    await writeBoard(payload);
  }

  const items = payload.items
    .slice(-120)
    .reverse()
    .map((item) => ({
      ...item,
      responses: Array.isArray(item.responses)
        ? item.responses.map((response, idx) => ({
            ...response,
            id: typeof response.id === "string" ? response.id : `${item.id}-r${idx}`,
            feedback:
              typeof response.feedback === "object" && response.feedback
                ? {
                    useful: Number((response.feedback as { useful?: number }).useful ?? 0),
                    notUseful: Number((response.feedback as { notUseful?: number }).notUseful ?? 0),
                  }
                : { useful: 0, notUseful: 0 },
          }))
        : [],
      requiredResponders: Array.isArray(item.requiredResponders) ? item.requiredResponders : [],
      researchContext: Array.isArray(item.researchContext) ? item.researchContext : [],
      slaMinutes: typeof item.slaMinutes === "number" ? item.slaMinutes : DEFAULT_SLA_MINUTES,
      escalatedAt: typeof item.escalatedAt === "string" ? item.escalatedAt : null,
      stale:
        item.type === "verification"
          ? (() => {
              const createdTs = Date.parse(item.createdAt);
              const ageMinutes = Number.isFinite(createdTs) ? Math.floor((now - createdTs) / 60_000) : 0;
              return pendingResponders(item).length > 0 && ageMinutes >= (item.slaMinutes ?? DEFAULT_SLA_MINUTES);
            })()
          : false,
      pendingResponders: pendingResponders(item),
      answered: pendingResponders(item).length === 0,
    }));

  return NextResponse.json({
    ok: true,
    items,
    verification: items.filter((item) => item.type === "verification"),
    ideas: items.filter((item) => item.type === "idea"),
  });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    action?: "create" | "answer" | "auto-answer" | "feedback" | "refresh-context" | "escalate";
    type?: string;
    message?: string;
    author?: string;
    itemId?: string;
    responder?: string;
    slaMinutes?: number;
    responseId?: string;
    responseIndex?: number;
    vote?: "useful" | "notUseful";
  };

  const action = body.action ?? "create";
  const payload = await readBoard();

  if (action === "feedback") {
    if (!body.itemId || !body.vote) {
      return NextResponse.json({ ok: false, error: "itemId and vote are required" }, { status: 400 });
    }
    const idx = payload.items.findIndex((item) => item.id === body.itemId);
    if (idx < 0) {
      return NextResponse.json({ ok: false, error: "item not found" }, { status: 404 });
    }
    const item = payload.items[idx];
    const responses = Array.isArray(item.responses) ? item.responses : [];
    const voteKey = body.vote === "notUseful" ? "notUseful" : "useful";
    const voteTarget = responses.findIndex((resp, responseIndex) => {
      if (typeof body.responseId === "string" && body.responseId.trim()) return resp.id === body.responseId;
      if (typeof body.responseIndex === "number") return responseIndex === body.responseIndex;
      return false;
    });
    if (voteTarget < 0) {
      return NextResponse.json({ ok: false, error: "response not found" }, { status: 404 });
    }
    const target = responses[voteTarget];
    const feedback = target.feedback ?? { useful: 0, notUseful: 0 };
    feedback[voteKey] += 1;
    responses[voteTarget] = { ...target, feedback };
    payload.items[idx] = { ...item, responses };
    await writeBoard(payload);
    return NextResponse.json({ ok: true, item: payload.items[idx] });
  }

  if (action === "refresh-context" || action === "escalate") {
    if (!body.itemId) {
      return NextResponse.json({ ok: false, error: "itemId is required" }, { status: 400 });
    }
    const idx = payload.items.findIndex((item) => item.id === body.itemId);
    if (idx < 0) {
      return NextResponse.json({ ok: false, error: "item not found" }, { status: 404 });
    }
    const item = payload.items[idx];
    if (item.type !== "verification") {
      return NextResponse.json({ ok: false, error: "action only valid for verification items" }, { status: 400 });
    }

    const { required, activity } = await responderPlan(item.message);
    item.requiredResponders = required;
    item.researchContext = await lookupMemoryContext(item.message, required);

    if (action === "escalate") {
      const backups = topResponderBackups(activity, item.requiredResponders ?? []).slice(0, ESCALATION_BATCH);
      if (backups.length > 0) {
        item.requiredResponders = [...(item.requiredResponders ?? []), ...backups].slice(0, ESCALATION_MAX_RESPONDERS);
        item.escalatedAt = new Date().toISOString();
        item.responses = [
          ...(item.responses ?? []),
          {
            id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
            responder: "System Escalation",
            message: `Manual escalation requested. Added: ${backups.join(", ")}.`,
            createdAt: item.escalatedAt,
            feedback: { useful: 0, notUseful: 0 },
          },
        ];
      }
    }

    payload.items[idx] = item;
    await writeBoard(payload);
    return NextResponse.json({ ok: true, item: payload.items[idx] });
  }

    if (action === "answer" || action === "auto-answer") {
    if (!body.itemId) {
      return NextResponse.json({ ok: false, error: "itemId is required" }, { status: 400 });
    }

    const idx = payload.items.findIndex((item) => item.id === body.itemId);
    if (idx < 0) {
      return NextResponse.json({ ok: false, error: "verification item not found" }, { status: 404 });
    }

    const item = payload.items[idx];
    if (item.type !== "verification") {
      return NextResponse.json({ ok: false, error: "answers are only supported for verification items" }, { status: 400 });
    }

    const { required, activity } = await responderPlan(item.message);
    const context = await lookupMemoryContext(item.message, required);
    const existing = new Set((item.responses ?? []).map((response) => response.responder));
    item.requiredResponders = required;
    item.researchContext = context;

    if (action === "answer") {
      const responder = (body.responder ?? "Agent").trim() || "Agent";
      const fallback = buildVerificationResponse(responder, item.message, activity[responder]);
      const message = (body.message ?? withContextMessage(fallback, responder, context)).trim();
      if (!existing.has(responder)) {
        item.responses = [
          ...(item.responses ?? []),
          {
            id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
            responder,
            message: message.slice(0, 500),
            createdAt: new Date().toISOString(),
            feedback: { useful: 0, notUseful: 0 },
          },
        ];
      }
    } else {
      const now = new Date().toISOString();
      const generated = required
        .filter((name) => !existing.has(name))
        .map((name) => {
          const fallback = buildVerificationResponse(name, item.message, activity[name]);
          return {
            id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
            responder: name,
            message: withContextMessage(fallback, name, context),
            createdAt: now,
            feedback: { useful: 0, notUseful: 0 },
          };
        });
      item.responses = [...(item.responses ?? []), ...generated];
    }

    payload.items[idx] = item;
    await writeBoard(payload);

    return NextResponse.json({
      ok: true,
      item: {
        ...item,
        pendingResponders: pendingResponders(item),
        answered: pendingResponders(item).length === 0,
      },
    });
  }

  if (!body.type || !isBoardType(body.type)) {
    return NextResponse.json({ ok: false, error: "type must be verification|idea" }, { status: 400 });
  }

  const message = (body.message ?? "").trim();
  const author = (body.author ?? "Agent").trim() || "Agent";

  if (message.length < 4) {
    return NextResponse.json({ ok: false, error: "message must be at least 4 chars" }, { status: 400 });
  }

  const now = new Date().toISOString();
  const { required, activity } = body.type === "verification" ? await responderPlan(message) : { required: [], activity: {} as Record<string, never> };
  const context = body.type === "verification" ? await lookupMemoryContext(message, required) : [];
  const slaMinutes = Math.max(1, Math.min(240, Number(body.slaMinutes ?? DEFAULT_SLA_MINUTES)));

  const next: BoardItem = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    type: body.type,
    author: author.slice(0, 40),
    message: message.slice(0, 500),
    createdAt: now,
    slaMinutes,
    requiredResponders: required,
    researchContext: context,
    responses:
      body.type === "verification"
        ? required.map((responder) => {
            const fallback = buildVerificationResponse(responder, message, activity[responder]);
            return {
              id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
              responder,
              message: withContextMessage(fallback, responder, context),
              createdAt: now,
              feedback: { useful: 0, notUseful: 0 },
            };
          })
        : [],
  };

  const items = [...payload.items, next].slice(-120);
  await writeBoard({ items });

  return NextResponse.json({
    ok: true,
    item: {
      ...next,
      pendingResponders: pendingResponders(next),
      answered: pendingResponders(next).length === 0,
    },
  });
}
