import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export type StatsAgent = {
  name: string;
  role: string;
  status?: string;
  model?: string | null;
  fitness?: number;
  task_success_rate?: number;
  knowledge_contrib?: number;
};

export type StatsPayload = {
  timestamp?: number;
  agents: StatsAgent[];
  resources: unknown[];
  feed: Array<{ time?: string; type?: string; summary?: string }>;
};

export type JobHistoryRecord = {
  id: string;
  agent: string;
  role: string;
  time?: string;
  summary: string;
  success: boolean | null;
  source: "stats-feed";
  recordedAt: string;
};

export type JobHistoryPayload = {
  jobs: JobHistoryRecord[];
};

export type AgentActivity = {
  name: string;
  currentJob: string;
  status: string;
  successRate: number;
  jobsCompleted: number;
  lastJobAt: string | null;
  recentJobs: Array<{ summary: string; success: boolean | null; time?: string }>;
};

const statsPath = path.join(process.cwd(), "public", "stats.json");
const jobsHistoryPath = path.join(process.cwd(), "data", "jobs-history.json");

function parseTaskSummary(summary: string): { agent: string; role: string; job: string; success: boolean | null } | null {
  const trimmed = summary.trim();
  const regex = /^>\s*(.+?)\s*\((.+?)\):\s*(.+?)\s*->\s*Success:\s*(True|False)$/i;
  const match = trimmed.match(regex);
  if (match) {
    return {
      agent: match[1].trim(),
      role: match[2].trim(),
      job: match[3].trim(),
      success: match[4].toLowerCase() === "true",
    };
  }

  const fallback = trimmed.match(/^>\s*(.+?):\s*(.+)$/);
  if (fallback) {
    return {
      agent: fallback[1].trim(),
      role: "Unknown",
      job: fallback[2].trim(),
      success: null,
    };
  }

  return null;
}

export async function readStatsPayload(): Promise<StatsPayload> {
  try {
    const raw = await readFile(statsPath, "utf-8");
    const json = JSON.parse(raw) as Partial<StatsPayload>;
    return {
      timestamp: json.timestamp,
      agents: Array.isArray(json.agents) ? (json.agents as StatsAgent[]) : [],
      resources: Array.isArray(json.resources) ? json.resources : [],
      feed: Array.isArray(json.feed) ? json.feed : [],
    };
  } catch {
    return { agents: [], resources: [], feed: [] };
  }
}

export async function readJobsHistory(): Promise<JobHistoryPayload> {
  try {
    const raw = await readFile(jobsHistoryPath, "utf-8");
    const json = JSON.parse(raw) as Partial<JobHistoryPayload>;
    return { jobs: Array.isArray(json.jobs) ? (json.jobs as JobHistoryRecord[]) : [] };
  } catch {
    return { jobs: [] };
  }
}

export async function writeJobsHistory(payload: JobHistoryPayload): Promise<void> {
  await mkdir(path.dirname(jobsHistoryPath), { recursive: true });
  await writeFile(jobsHistoryPath, JSON.stringify(payload, null, 2), "utf-8");
}

export async function ingestStatsFeedToHistory(stats: StatsPayload): Promise<JobHistoryPayload> {
  const history = await readJobsHistory();
  const existing = new Set(history.jobs.map((job) => job.id));

  for (const item of stats.feed) {
    const summary = (item.summary ?? "").trim();
    if (!summary || (item.type ?? "") !== "Task") continue;

    const parsed = parseTaskSummary(summary);
    if (!parsed) continue;

    const id = `${item.time ?? "na"}|${parsed.agent}|${parsed.job}`;
    if (existing.has(id)) continue;

    history.jobs.push({
      id,
      agent: parsed.agent,
      role: parsed.role,
      time: item.time,
      summary: parsed.job,
      success: parsed.success,
      source: "stats-feed",
      recordedAt: new Date().toISOString(),
    });
    existing.add(id);
  }

  history.jobs = history.jobs.slice(-25000);
  await writeJobsHistory(history);
  return history;
}

export function buildActivityByAgent(stats: StatsPayload, history: JobHistoryPayload): Record<string, AgentActivity> {
  const map: Record<string, AgentActivity> = {};

  for (const agent of stats.agents) {
    const name = agent.name?.trim();
    if (!name) continue;
    map[name] = {
      name,
      currentJob: `${agent.role} telemetry synchronization`,
      status: agent.status ?? "Idle",
      successRate: typeof agent.task_success_rate === "number" ? agent.task_success_rate : 0,
      jobsCompleted: 0,
      lastJobAt: null,
      recentJobs: [],
    };
  }

  const byAgent = new Map<string, JobHistoryRecord[]>();
  for (const job of history.jobs) {
    const list = byAgent.get(job.agent) ?? [];
    list.push(job);
    byAgent.set(job.agent, list);
  }

  for (const [agentName, jobs] of byAgent.entries()) {
    jobs.sort((a, b) => String(a.recordedAt).localeCompare(String(b.recordedAt)));
    const existing = map[agentName] ?? {
      name: agentName,
      currentJob: "No recent task",
      status: "Unknown",
      successRate: 0,
      jobsCompleted: 0,
      lastJobAt: null,
      recentJobs: [],
    };

    const recent = jobs.slice(-6).reverse();
    const successful = jobs.filter((job) => job.success === true).length;
    const comparable = jobs.filter((job) => job.success !== null).length;
    const computedRate = comparable > 0 ? Number(((successful / comparable) * 100).toFixed(1)) : existing.successRate;

    existing.jobsCompleted = jobs.length;
    existing.recentJobs = recent.map((job) => ({ summary: job.summary, success: job.success, time: job.time }));
    existing.currentJob = recent[0]?.summary ?? existing.currentJob;
    existing.lastJobAt = recent[0]?.recordedAt ?? null;
    existing.successRate = typeof existing.successRate === "number" && existing.successRate > 0 ? existing.successRate : computedRate;
    map[agentName] = existing;
  }

  return map;
}

export function extractMentionedAgents(message: string, agentNames: string[]): string[] {
  const text = message.toLowerCase();
  const mentions = agentNames.filter((name) => {
    const normalized = name.toLowerCase().trim();
    return normalized.length > 0 && text.includes(normalized);
  });
  return [...new Set(mentions)];
}

export function buildVerificationResponse(agentName: string, question: string, activity?: AgentActivity): string {
  if (!activity) {
    return `${agentName}: I can see your request. I do not have task telemetry yet, but I am checking now -> ${question.slice(0, 120)}`;
  }

  const latest = activity.recentJobs[0];
  const successText = `${activity.successRate.toFixed(1)}% success over ${activity.jobsCompleted} completed jobs`;
  const latestText = latest ? ` Latest task: ${latest.summary}${latest.success === null ? "" : latest.success ? " (success)" : " (failed)"}.` : " No recent task found.";
  return `${agentName}: I received your verification request. Current work: ${activity.currentJob}. ${successText}.${latestText}`;
}
