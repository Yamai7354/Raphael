"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AgentPulse } from "@/components/AgentPulse";
import { ResourceMonitor } from "@/components/ResourceMonitor";
import { CognitiveFeed } from "@/components/CognitiveFeed";
import {
  ShieldCheck,
  Zap,
  Globe,
  Play,
  Square,
  Activity,
  Loader2,
  ChevronLeft,
  ChevronRight,
  MessageSquareQuote,
  MessageSquarePlus,
  Hammer,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

type Agent = {
  name: string;
  role: string;
  status: string;
  model: string | null;
  fitness?: number;
  task_success_rate?: number;
  globalRank?: number;
  mission?: string | null;
};

type DashboardData = {
  agents: Agent[];
  resources: Array<{ name: string; cpu: number; ram: number; vram: number }>;
  feed: Array<{ time: string; type: "Observation" | "Task" | "Manual Override" | "Event"; summary: string }>;
  priority_engine?: {
    evaluations?: number;
    latest_action?: string;
    latest_signals?: Record<string, boolean>;
    manual_override?: boolean;
    active_missions?: number;
  };
};

type AnalyticsMetrics = {
  totalAgents: number;
  activeAgents: number;
  idleAgents: number;
  averageFitness: number;
  manualOverrides: number;
  cpu: number;
  ram: number;
  vram: number;
};

type GraphNode = { id: string; label: string; type: "agent" | "role" | "event"; x: number; y: number; score?: number };
type Job = {
  name: string;
  role: string;
  status: string;
  currentJob: string;
  updatedAt: string | null;
  projection: Array<{ step: number; projectedFitness: number }>;
};
type SystemComponent = { id: string; name: string; up: boolean; detail: string };
type Toast = { tone: "success" | "error" | "info"; message: string } | null;
type ApiHealth = { id: string; label: string; up: boolean; status: number | null };
type GraphSource = "neo4j" | "fallback" | "unknown";
type BoardResponse = {
  id?: string;
  responder: string;
  message: string;
  createdAt: string;
  feedback?: { useful: number; notUseful: number };
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
type BoardItem = {
  id: string;
  type: "verification" | "idea";
  author: string;
  message: string;
  createdAt: string;
  requiredResponders?: string[];
  responses?: BoardResponse[];
  pendingResponders?: string[];
  answered?: boolean;
  stale?: boolean;
  escalatedAt?: string | null;
  slaMinutes?: number;
  researchContext?: MemoryContextHit[];
};
type FactoryReport = {
  scores?: {
    completion?: number;
    structure_quality?: number;
    relationship_quality?: number;
    goal_alignment?: number;
    overall?: number;
  };
  delivered?: { created_agents?: string[]; graph_agents?: number; database_agents?: number; factory_agent?: string };
  requested?: { goal?: string };
  feedback?: string[];
  generated_at?: string;
};
type AgentActivity = {
  currentJob: string;
  successRate: number;
  jobsCompleted: number;
  recentJobs: Array<{ summary: string; success: boolean | null; time?: string }>;
};
type MemoryTrace = {
  total_queries: number;
  avg_latency_ms: number;
  hit_rate_pct: number;
  top_missed_queries: Array<{ query: string; misses: number }>;
};
type NightlyMaintenanceStatus = {
  lastRunAt: string | null;
  skipped?: boolean;
};
type PrioritySignalState = {
  graph_too_large?: boolean;
  no_new_features?: boolean;
  memory_quality_dropping?: boolean;
  system_idle?: boolean;
};
type PriorityEvaluation = {
  action?: string;
  details?: string;
  manual_override?: boolean;
  spawned_agents?: number;
  mission_assignments?: number;
  signals?: PrioritySignalState;
};
type PriorityMission = {
  agent: string;
  mission: string;
  assignedAt: string | null;
  reason: string | null;
};
type PriorityStatus = {
  evaluationsCount: number;
  latestEvaluation: PriorityEvaluation | null;
  activeMissions: PriorityMission[];
  missionCount: number;
};

async function readJsonSafe<T>(res: Response): Promise<T | null> {
  try {
    const text = await res.text();
    if (!text) return null;
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

export default function Home() {
  const [data, setData] = useState<DashboardData>({ agents: [], resources: [], feed: [] });
  const [analytics, setAnalytics] = useState<AnalyticsMetrics>({
    totalAgents: 0,
    activeAgents: 0,
    idleAgents: 0,
    averageFitness: 0,
    manualOverrides: 0,
    cpu: 0,
    ram: 0,
    vram: 0,
  });
  const [swarmRunning, setSwarmRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState<null | "start" | "stop" | "start-all">(null);

  const [kgLimit, setKgLimit] = useState(24);
  const [kgNodes, setKgNodes] = useState<GraphNode[]>([]);
  const [graphSource, setGraphSource] = useState<GraphSource>("unknown");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobIndex, setJobIndex] = useState(0);
  const [systemComponents, setSystemComponents] = useState<SystemComponent[]>([]);
  const [resetting, setResetting] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<Toast>(null);
  const [apiHealth, setApiHealth] = useState<ApiHealth[]>([
    { id: "swarm", label: "/api/swarm", up: false, status: null },
    { id: "agents", label: "/api/agents", up: false, status: null },
    { id: "system", label: "/api/system-status", up: false, status: null },
  ]);
  const [verificationItems, setVerificationItems] = useState<BoardItem[]>([]);
  const [ideaItems, setIdeaItems] = useState<BoardItem[]>([]);
  const [verificationDraft, setVerificationDraft] = useState("");
  const [ideaDraft, setIdeaDraft] = useState("");
  const [boardBusy, setBoardBusy] = useState<null | "verification" | "idea">(null);
  const [factoryBusy, setFactoryBusy] = useState(false);
  const [factoryReport, setFactoryReport] = useState<FactoryReport | null>(null);
  const [factoryGoal, setFactoryGoal] = useState("");
  const [agentActivity, setAgentActivity] = useState<Record<string, AgentActivity>>({});
  const [memoryTrace, setMemoryTrace] = useState<MemoryTrace | null>(null);
  const [feedbackBusy, setFeedbackBusy] = useState<string | null>(null);
  const [verificationActionBusy, setVerificationActionBusy] = useState<string | null>(null);
  const [nightlyStatus, setNightlyStatus] = useState<NightlyMaintenanceStatus>({ lastRunAt: null });
  const [nightlyBusy, setNightlyBusy] = useState(false);
  const [priorityStatus, setPriorityStatus] = useState<PriorityStatus>({
    evaluationsCount: 0,
    latestEvaluation: null,
    activeMissions: [],
    missionCount: 0,
  });
  const [priorityBusy, setPriorityBusy] = useState<string | null>(null);
  const pollInFlight = useRef(false);

  const showToast = (tone: "success" | "error" | "info", message: string) => {
    setToast({ tone, message });
  };

  const fetchDashboard = async () => {
    try {
      const [statsRes, analyticsRes, swarmRes, jobsRes, systemRes] = await Promise.all([
        fetch("/stats.json", { cache: "no-store" }),
        fetch("/api/analytics", { cache: "no-store" }),
        fetch("/api/swarm", { cache: "no-store" }),
        fetch("/api/agent-jobs", { cache: "no-store" }),
        fetch("/api/system-status", { cache: "no-store" }),
      ]);
      const agentsProbe = await fetch("/api/agents", { cache: "no-store" });

      setApiHealth([
        { id: "swarm", label: "/api/swarm", up: swarmRes.ok, status: swarmRes.status },
        { id: "agents", label: "/api/agents", up: agentsProbe.ok, status: agentsProbe.status },
        { id: "system", label: "/api/system-status", up: systemRes.ok, status: systemRes.status },
      ]);

      if (statsRes.ok) {
        const json = await readJsonSafe<DashboardData>(statsRes);
        setData({
          agents: Array.isArray(json?.agents) ? json.agents : [],
          resources: Array.isArray(json?.resources) ? json.resources : [],
          feed: Array.isArray(json?.feed) ? json.feed : [],
        });
      }
      if (analyticsRes.ok) {
        const json = await readJsonSafe<{ metrics?: AnalyticsMetrics }>(analyticsRes);
        setAnalytics(json?.metrics ?? analytics);
      }
      if (swarmRes.ok) {
        const json = await readJsonSafe<{ running?: boolean }>(swarmRes);
        setSwarmRunning(Boolean(json?.running));
      }
      if (jobsRes.ok) {
        const json = await readJsonSafe<{ jobs?: Job[] }>(jobsRes);
        setJobs(Array.isArray(json?.jobs) ? json.jobs : []);
      }
      if (systemRes.ok) {
        const json = await readJsonSafe<{ components?: SystemComponent[] }>(systemRes);
        setSystemComponents(Array.isArray(json?.components) ? json.components : []);
      }
    } catch (e) {
      console.error("Failed to fetch dashboard telemetry:", e);
      setApiHealth((current) => current.map((item) => ({ ...item, up: false, status: null })));
    } finally {
      setLoading(false);
    }
  };

  const fetchCollabBoard = async () => {
    try {
      const res = await fetch("/api/collab-board", { cache: "no-store" });
      if (!res.ok) return;
      const json = await readJsonSafe<{ verification?: BoardItem[]; ideas?: BoardItem[] }>(res);
      setVerificationItems(Array.isArray(json?.verification) ? json.verification.slice(0, 8) : []);
      setIdeaItems(Array.isArray(json?.ideas) ? json.ideas.slice(0, 8) : []);
    } catch {
      // Keep dashboard resilient if board data is unavailable.
    }
  };

  const fetchFactoryReport = async () => {
    try {
      const res = await fetch("/api/agent-factory", { cache: "no-store" });
      if (!res.ok) return;
      const json = await readJsonSafe<{ report?: FactoryReport | null }>(res);
      setFactoryReport(json?.report ?? null);
    } catch {
      // Keep dashboard resilient if factory report is unavailable.
    }
  };

  const fetchAgentActivity = async () => {
    try {
      const res = await fetch("/api/agent-activity", { cache: "no-store" });
      if (!res.ok) return;
      const json = await readJsonSafe<{ activity?: Record<string, AgentActivity> }>(res);
      setAgentActivity(json?.activity ?? {});
    } catch {
      // Keep dashboard resilient if activity data is unavailable.
    }
  };

  const fetchMemoryTrace = async () => {
    try {
      const res = await fetch("/api/memory/trace?windowDays=1", { cache: "no-store" });
      if (!res.ok) return;
      const json = await readJsonSafe<{ trace?: MemoryTrace }>(res);
      setMemoryTrace(json?.trace ?? null);
    } catch {
      // Keep dashboard resilient if memory trace is unavailable.
    }
  };

  const fetchNightlyStatus = async () => {
    try {
      const res = await fetch("/api/memory/nightly", { cache: "no-store" });
      if (!res.ok) return;
      const json = await readJsonSafe<{ history?: { runs?: Array<{ ranAt?: string }> } }>(res);
      const runs = Array.isArray(json?.history?.runs) ? json?.history?.runs : [];
      const lastRunAt = runs.length > 0 ? (runs[runs.length - 1]?.ranAt ?? null) : null;
      setNightlyStatus({ lastRunAt });
    } catch {
      // Keep dashboard resilient if maintenance history is unavailable.
    }
  };

  const fetchPriorityStatus = async () => {
    try {
      const res = await fetch("/api/priority", { cache: "no-store" });
      if (!res.ok) return;
      const json = await readJsonSafe<{
        evaluationsCount?: number;
        latestEvaluation?: PriorityEvaluation | null;
        activeMissions?: PriorityMission[];
        missionCount?: number;
      }>(res);
      setPriorityStatus({
        evaluationsCount: Number(json?.evaluationsCount ?? 0),
        latestEvaluation: json?.latestEvaluation ?? null,
        activeMissions: Array.isArray(json?.activeMissions) ? json.activeMissions : [],
        missionCount: Number(json?.missionCount ?? 0),
      });
    } catch {
      // Keep dashboard resilient if priority data is unavailable.
    }
  };

  const runNightlyMaintenance = async () => {
    setNightlyBusy(true);
    try {
      const res = await fetch("/api/memory/nightly", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: true }),
      });
      const json = await readJsonSafe<{ ok?: boolean; skipped?: boolean; ranAt?: string }>(res);
      if (!res.ok || json?.ok === false) {
        throw new Error("Nightly maintenance failed");
      }
      setNightlyStatus({ lastRunAt: json?.ranAt ?? new Date().toISOString(), skipped: json?.skipped });
      await fetchMemoryTrace();
      showToast("success", json?.skipped ? "Nightly skipped (recent run)" : "Nightly maintenance completed");
    } catch (error) {
      showToast("error", error instanceof Error ? error.message : "Nightly maintenance failed");
    } finally {
      setNightlyBusy(false);
    }
  };

  const fetchKnowledgeGraph = async (limit: number) => {
    try {
      const res = await fetch(`/api/knowledge-graph?limit=${limit}`, { cache: "no-store" });
      if (!res.ok) return;
      const json = await readJsonSafe<{ nodes?: GraphNode[]; summary?: { source?: string } }>(res);
      setKgNodes(Array.isArray(json?.nodes) ? json.nodes : []);
      if (json?.summary?.source === "neo4j") {
        setGraphSource("neo4j");
      } else if (json?.summary?.source === "fallback") {
        setGraphSource("fallback");
      } else {
        setGraphSource("unknown");
      }
    } catch (error) {
      console.error(error);
      setGraphSource("unknown");
    }
  };

  const controlSwarm = async (action: "start" | "stop") => {
    setActionBusy(action);
    try {
      const res = await fetch("/api/swarm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(payload?.detail || payload?.error || `Failed to ${action} swarm`);
      }
      await fetchDashboard();
      showToast("success", payload?.message || `Swarm ${action}ed`);
    } catch (error) {
      console.error(error);
      showToast("error", error instanceof Error ? error.message : "Swarm control failed");
    } finally {
      setActionBusy(null);
    }
  };

  const startAllAgents = async () => {
    setActionBusy("start-all");
    try {
      const res = await fetch("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "start-all" }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(payload?.error || "Failed to start all agents");
      }
      await fetchDashboard();
      showToast("success", payload?.message || "Started all agents");
    } catch (error) {
      console.error(error);
      showToast("error", error instanceof Error ? error.message : "Agent start failed");
    } finally {
      setActionBusy(null);
    }
  };

  const resetComponent = async (componentId: string) => {
    setResetting((current) => ({ ...current, [componentId]: true }));
    try {
      const res = await fetch("/api/system-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ componentId }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.error || "Reset failed");
      }
      const json = await res.json();
      setSystemComponents(Array.isArray(json?.components) ? json.components : []);
      showToast("success", `Reset ${componentId}`);
    } catch (error) {
      console.error(error);
      showToast("error", error instanceof Error ? error.message : "Reset failed");
    } finally {
      setResetting((current) => ({ ...current, [componentId]: false }));
    }
  };

  const submitBoardItem = async (type: "verification" | "idea") => {
    const message = type === "verification" ? verificationDraft.trim() : ideaDraft.trim();
    if (message.length < 4) {
      showToast("error", "Message is too short");
      return;
    }
    setBoardBusy(type);
    try {
      const res = await fetch("/api/collab-board", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, message, author: "Operator" }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(payload?.error || "Failed to post message");
      }
      if (type === "verification") {
        setVerificationDraft("");
      } else {
        setIdeaDraft("");
      }
      await fetchCollabBoard();
      showToast("success", type === "verification" ? "Verification note posted" : "Idea posted");
    } catch (error) {
      showToast("error", error instanceof Error ? error.message : "Failed to post");
    } finally {
      setBoardBusy(null);
    }
  };

  const sendResponseFeedback = async (itemId: string, responseId: string | undefined, responseIndex: number, vote: "useful" | "notUseful") => {
    const busyKey = `${itemId}:${responseId ?? responseIndex}:${vote}`;
    setFeedbackBusy(busyKey);
    try {
      const res = await fetch("/api/collab-board", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "feedback",
          itemId,
          responseId,
          responseIndex,
          vote,
        }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(payload?.error || "Failed to record feedback");
      }
      await fetchCollabBoard();
    } catch (error) {
      showToast("error", error instanceof Error ? error.message : "Feedback failed");
    } finally {
      setFeedbackBusy(null);
    }
  };

  const runVerificationAction = async (itemId: string, action: "escalate" | "refresh-context") => {
    const busyKey = `${itemId}:${action}`;
    setVerificationActionBusy(busyKey);
    try {
      const res = await fetch("/api/collab-board", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, itemId }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(payload?.error || "Action failed");
      }
      await fetchCollabBoard();
      showToast("success", action === "escalate" ? "Escalated verification" : "Context refreshed");
    } catch (error) {
      showToast("error", error instanceof Error ? error.message : "Verification action failed");
    } finally {
      setVerificationActionBusy(null);
    }
  };

  const runAgentFactory = async () => {
    setFactoryBusy(true);
    try {
      const res = await fetch("/api/agent-factory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: factoryGoal.trim() }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok || payload?.ok === false) {
        throw new Error(payload?.error || "Agent factory failed");
      }
      setFactoryReport((payload?.report as FactoryReport | undefined) ?? null);
      await fetchDashboard();
      showToast("success", "Agent factory completed");
    } catch (error) {
      showToast("error", error instanceof Error ? error.message : "Agent factory failed");
    } finally {
      setFactoryBusy(false);
    }
  };

  const runPriorityAction = async (action: string) => {
    setPriorityBusy(action);
    try {
      const res = await fetch("/api/priority", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const payload = await readJsonSafe<{ ok?: boolean; error?: string; message?: string }>(res);
      if (!res.ok || payload?.ok === false) {
        throw new Error(payload?.error || "Priority action failed");
      }
      showToast("success", payload?.message || "Priority action queued");
      await Promise.all([fetchPriorityStatus(), fetchDashboard()]);
    } catch (error) {
      showToast("error", error instanceof Error ? error.message : "Priority action failed");
    } finally {
      setPriorityBusy(null);
    }
  };

  useEffect(() => {
    const refresh = async () => {
      if (pollInFlight.current) return;
      pollInFlight.current = true;
      try {
        await Promise.all([
          fetchDashboard(),
          fetchKnowledgeGraph(kgLimit),
          fetchCollabBoard(),
          fetchFactoryReport(),
          fetchAgentActivity(),
          fetchMemoryTrace(),
          fetchNightlyStatus(),
          fetchPriorityStatus(),
        ]);
      } finally {
        pollInFlight.current = false;
      }
    };

    refresh();
    const interval = setInterval(() => {
      refresh();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchKnowledgeGraph(kgLimit);
  }, [kgLimit]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 2600);
    return () => window.clearTimeout(id);
  }, [toast]);

  useEffect(() => {
    if (jobs.length === 0) {
      setJobIndex(0);
      return;
    }
    if (jobIndex >= jobs.length) {
      setJobIndex(0);
    }
  }, [jobs, jobIndex]);

  const sortedAgents = useMemo(
    () =>
      [...(data.agents || [])]
        .map((agent) => {
          const name = agent.name.trim();
          const activity = agentActivity[name];
          const jobsCompleted = activity?.jobsCompleted ?? 0;
          const successRate = Number(activity?.successRate ?? agent.task_success_rate ?? 0);
          const fitness = Number(agent.fitness ?? 0);

          const sampleSizeBoost = Math.min(6, Math.log10(jobsCompleted + 1) * 6);
          const lowSamplePenalty = jobsCompleted === 0 ? 28 : jobsCompleted < 5 ? 12 : jobsCompleted < 10 ? 6 : 0;
          const zeroSuccessPenalty = successRate <= 0.1 ? 22 : 0;
          const rankingScore = (fitness * 0.55) + (successRate * 0.4) + sampleSizeBoost - lowSamplePenalty - zeroSuccessPenalty;

          return {
            ...agent,
            name,
            task_success_rate: successRate,
            rankingScore,
            jobsCompleted,
          };
        })
        .sort((a, b) => b.rankingScore - a.rankingScore)
        .map((agent, idx) => ({ ...agent, globalRank: idx + 1 })),
    [data.agents, agentActivity]
  );

  const top10Agents = sortedAgents.slice(0, 10);
  const mvp = sortedAgents[0] ?? null;
  const currentJob = jobs[jobIndex] ?? null;
  const graphPoints = kgNodes.map((node) => ({ x: node.x, y: node.y, z: node.type === "agent" ? 200 : node.type === "role" ? 160 : 120 }));
  const latestPriority = priorityStatus.latestEvaluation;
  const prioritySignals = latestPriority?.signals ?? data.priority_engine?.latest_signals ?? {};
  const priorityLatestAction = latestPriority?.action ?? data.priority_engine?.latest_action ?? "maintain";

  const roleLeaders = useMemo(
    () =>
      ["Researcher", "Analyst", "Creative Coder", "Communicator", "Explorer"].reduce<Array<{ role: string; leader: Agent }>>(
        (acc, role) => {
          const leader = sortedAgents.find((agent) => agent.role === role);
          if (leader) acc.push({ role, leader });
          return acc;
        },
        []
      ),
    [sortedAgents]
  );

  if (loading) {
    return (
      <div className="flex h-full min-h-[60vh] items-center justify-center text-primary font-mono animate-pulse">
        Initializing Swarm Mastery OS...
      </div>
    );
  }

  return (
    <>
      <header className="flex flex-col gap-4 mb-12 xl:flex-row xl:justify-between xl:items-center">
        <div>
          <h1 className="text-4xl font-bold premium-gradient-text uppercase tracking-tighter">Command Center</h1>
          <p className="text-muted-foreground mt-2 font-mono text-xs opacity-60">RAPHAEL_SWARM_TELEMETRY_v2.2.0</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => controlSwarm("start")}
            disabled={actionBusy !== null || swarmRunning}
            variant="outline"
            size="sm"
            className="border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 hover:text-primary uppercase tracking-wider"
          >
            {actionBusy === "start" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Start Swarm
          </Button>
          <Button
            onClick={() => controlSwarm("stop")}
            disabled={actionBusy !== null || !swarmRunning}
            variant="destructive"
            size="sm"
            className="uppercase tracking-wider"
          >
            {actionBusy === "stop" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Square className="w-4 h-4" />} Stop Swarm
          </Button>
          <Button
            onClick={startAllAgents}
            disabled={actionBusy !== null || data.agents.length === 0}
            variant="outline"
            size="sm"
            className="border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white uppercase tracking-wider"
          >
            {actionBusy === "start-all" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />} Start All Agents
          </Button>
        </div>
      </header>
      {toast && (
        <div
          className={`fixed top-5 right-5 z-[90] rounded-xl border px-4 py-3 text-xs font-bold uppercase tracking-wider ${
            toast.tone === "success"
              ? "border-green-500/30 bg-green-500/15 text-green-200"
              : toast.tone === "error"
                ? "border-red-500/35 bg-red-500/15 text-red-200"
                : "border-primary/30 bg-primary/15 text-primary"
          }`}
        >
          {toast.message}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="glass-card-sm flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-green-500 shrink-0" />
          <div>
            <p className="text-[10px] uppercase text-muted-foreground tracking-widest">Health</p>
            <p className="text-sm font-bold">{swarmRunning ? "RUNNING" : "IDLE"}</p>
          </div>
        </div>
        <div className="glass-card-sm flex items-center gap-3">
          <Activity className="w-5 h-5 text-amber-500 shrink-0" />
          <div>
            <p className="text-[10px] uppercase text-muted-foreground tracking-widest">Agents</p>
            <p className="text-sm font-bold tracking-tighter">
              {analytics.activeAgents}/{analytics.totalAgents} ACTIVE
            </p>
          </div>
        </div>
        <div className="glass-card-sm flex items-center gap-3 border-primary/20 bg-primary/5">
          <Globe className="w-5 h-5 text-primary shrink-0" />
          <div>
            <p className="text-[10px] uppercase text-muted-foreground tracking-widest">Current MVP</p>
            <p className="text-sm font-bold truncate max-w-[120px]">{mvp?.name || "---"}</p>
          </div>
        </div>
        <div className="glass-card-sm flex items-center gap-3">
          <Zap className="w-5 h-5 text-primary shrink-0" />
          <div>
            <p className="text-[10px] uppercase text-muted-foreground tracking-widest">Avg Fitness</p>
            <p className="text-sm font-bold tracking-tighter">{analytics.averageFitness.toFixed(1)}%</p>
          </div>
        </div>
      </div>
      <section className="glass-card mb-8">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Diagnostics</h2>
          <button
            onClick={fetchDashboard}
            className="px-3 py-1.5 rounded-lg border border-white/20 bg-white/5 text-[10px] font-bold uppercase tracking-wider"
          >
            Recheck
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {apiHealth.map((api) => (
            <div
              key={api.id}
              className={`rounded-xl border p-3 ${
                api.up ? "border-green-500/30 bg-green-500/10" : "border-red-500/30 bg-red-500/10"
              }`}
            >
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{api.label}</p>
              <p className="text-xs font-bold mt-1">{api.up ? "Reachable" : "Unavailable"}</p>
              <p className="text-[10px] opacity-70 mt-1">{api.status ? `HTTP ${api.status}` : "No response"}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3">
          <p className="text-[10px] uppercase tracking-wider text-cyan-300">Memory Query Trace (24h)</p>
          <div className="mt-1 flex flex-wrap gap-4 text-xs">
            <span>Total: {memoryTrace?.total_queries ?? 0}</span>
            <span>Hit rate: {(memoryTrace?.hit_rate_pct ?? 0).toFixed(1)}%</span>
            <span>Avg latency: {(memoryTrace?.avg_latency_ms ?? 0).toFixed(1)}ms</span>
          </div>
          <p className="text-[10px] text-cyan-100/80 mt-1">
            Top misses:{" "}
            {(memoryTrace?.top_missed_queries ?? [])
              .slice(0, 2)
              .map((q) => `${q.query} (${q.misses})`)
              .join(" | ") || "none"}
          </p>
          <div className="mt-2 flex items-center justify-between">
            <p className="text-[10px] text-cyan-100/80">
              Last nightly: {nightlyStatus.lastRunAt ? new Date(nightlyStatus.lastRunAt).toLocaleString() : "never"}
            </p>
            <button
              type="button"
              onClick={runNightlyMaintenance}
              disabled={nightlyBusy}
              className="rounded border border-cyan-400/30 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase tracking-wide text-cyan-100 disabled:opacity-40"
            >
              {nightlyBusy ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null} Run Nightly
            </button>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-10">
        <section className="glass-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Knowledge Graph</h2>
            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-1 rounded-md border text-[10px] uppercase tracking-wider font-bold ${
                  graphSource === "neo4j"
                    ? "border-green-500/30 bg-green-500/10 text-green-300"
                    : graphSource === "fallback"
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                      : "border-white/20 bg-white/5 text-muted-foreground"
                }`}
              >
                Source: {graphSource}
              </span>
              <span className="text-[10px] uppercase text-muted-foreground">{kgNodes.length} visible nodes</span>
            </div>
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground">Node Visibility: {kgLimit}</label>
            <input
              type="range"
              min={5}
              max={60}
              value={kgLimit}
              onChange={(event) => setKgLimit(Number(event.target.value))}
              className="w-full mt-2"
            />
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <XAxis dataKey="x" type="number" domain={[0, 100]} hide />
                <YAxis dataKey="y" type="number" domain={[0, 100]} hide />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={graphPoints} fill="#60a5fa" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="glass-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Active Job Monitor</h2>
            <div className="flex gap-2">
              <button
                onClick={() => setJobIndex((index) => (jobs.length === 0 ? 0 : (index - 1 + jobs.length) % jobs.length))}
                className="p-2 rounded-lg border border-white/10 bg-white/5"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setJobIndex((index) => (jobs.length === 0 ? 0 : (index + 1) % jobs.length))}
                className="p-2 rounded-lg border border-white/10 bg-white/5"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
          {currentJob ? (
            <>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-1">
                <p className="text-sm font-bold">{currentJob.name}</p>
                <p className="text-[10px] uppercase text-muted-foreground tracking-wider">{currentJob.role}</p>
                <p className="text-xs text-white/80">{currentJob.currentJob}</p>
                <p className="text-[10px] uppercase tracking-wider text-primary">Status: {currentJob.status}</p>
              </div>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={currentJob.projection}>
                    <XAxis dataKey="step" stroke="#666" fontSize={10} />
                    <YAxis stroke="#666" fontSize={10} />
                    <Tooltip />
                    <Line type="monotone" dataKey="projectedFitness" stroke="#22c55e" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          ) : (
            <div className="rounded-xl border border-white/10 bg-white/5 p-6 text-center text-xs text-muted-foreground">
              No active job telemetry available.
            </div>
          )}
        </section>

        <section className="glass-card space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">System Status & Reset</h2>
          <div className="space-y-3">
            {systemComponents.map((component) => {
              const loadingReset = Boolean(resetting[component.id]);
              const up = component.up;
              return (
                <button
                  key={component.id}
                  onClick={() => resetComponent(component.id)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
                    loadingReset
                      ? "border-yellow-400/40 bg-yellow-500/15"
                      : up
                        ? "border-green-500/30 bg-green-500/10"
                        : "border-red-500/30 bg-red-500/10"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wide">{component.name}</span>
                    <span className="text-[10px] uppercase tracking-wider font-bold">
                      {loadingReset ? "Loading" : up ? "Up" : "Down"}
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground mt-1">{loadingReset ? "Reset in progress..." : component.detail}</p>
                </button>
              );
            })}
          </div>
        </section>

        <section className="glass-card space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Priority Engine</h2>
          <div className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-2">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Latest Action</p>
            <p className="text-sm font-bold">{priorityLatestAction}</p>
            <p className="text-[11px] text-white/80">{latestPriority?.details ?? "No recent decision details."}</p>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Evaluations: {priorityStatus.evaluationsCount} • Missions: {priorityStatus.missionCount}
            </p>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
              Manual override: {latestPriority?.manual_override ? "yes" : "no"}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] uppercase tracking-wide">
            <div className={`rounded border px-2 py-1 ${prioritySignals.graph_too_large ? "border-red-500/40 bg-red-500/15" : "border-white/15 bg-white/5"}`}>
              graph pressure
            </div>
            <div
              className={`rounded border px-2 py-1 ${
                prioritySignals.memory_quality_dropping ? "border-amber-500/40 bg-amber-500/15" : "border-white/15 bg-white/5"
              }`}
            >
              memory quality
            </div>
            <div className={`rounded border px-2 py-1 ${prioritySignals.no_new_features ? "border-cyan-500/40 bg-cyan-500/15" : "border-white/15 bg-white/5"}`}>
              feature flow
            </div>
            <div className={`rounded border px-2 py-1 ${prioritySignals.system_idle ? "border-blue-500/40 bg-blue-500/15" : "border-white/15 bg-white/5"}`}>
              system idle
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => runPriorityAction("spawn_compression_agents")}
              disabled={priorityBusy !== null}
              className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] uppercase tracking-wide disabled:opacity-40"
            >
              {priorityBusy === "spawn_compression_agents" ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null} Compress
            </button>
            <button
              onClick={() => runPriorityAction("spawn_coding_agents")}
              disabled={priorityBusy !== null}
              className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[10px] uppercase tracking-wide disabled:opacity-40"
            >
              {priorityBusy === "spawn_coding_agents" ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null} Code Push
            </button>
            <button
              onClick={() => runPriorityAction("spawn_evaluators")}
              disabled={priorityBusy !== null}
              className="rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-1 text-[10px] uppercase tracking-wide disabled:opacity-40"
            >
              {priorityBusy === "spawn_evaluators" ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null} Evaluate
            </button>
            <button
              onClick={() => runPriorityAction("allow_research_mode")}
              disabled={priorityBusy !== null}
              className="rounded border border-green-500/30 bg-green-500/10 px-2 py-1 text-[10px] uppercase tracking-wide disabled:opacity-40"
            >
              {priorityBusy === "allow_research_mode" ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null} Research
            </button>
          </div>
          <button
            onClick={() => runPriorityAction("assign_boredom_missions")}
            disabled={priorityBusy !== null}
            className="w-full rounded border border-primary/30 bg-primary/10 px-2 py-1 text-[10px] uppercase tracking-wide disabled:opacity-40"
          >
            {priorityBusy === "assign_boredom_missions" ? <Loader2 className="w-3 h-3 animate-spin inline" /> : null} Assign Boredom Missions
          </button>
          <div className="rounded-xl border border-white/10 bg-black/20 p-2 max-h-28 overflow-auto">
            {(priorityStatus.activeMissions ?? []).length === 0 ? (
              <p className="text-[11px] text-muted-foreground">No active missions yet.</p>
            ) : (
              (priorityStatus.activeMissions ?? []).slice(0, 6).map((entry) => (
                <p key={`${entry.agent}:${entry.mission}`} className="text-[11px] text-white/85">
                  {entry.agent}: {entry.mission}
                </p>
              ))
            )}
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-10">
        <section className="glass-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Verification Queue</h2>
            <MessageSquareQuote className="w-4 h-4 text-primary" />
          </div>
          <div className="space-y-2 max-h-56 overflow-auto pr-1">
            {verificationItems.length === 0 ? (
              <p className="text-xs text-muted-foreground">No verification questions posted yet.</p>
            ) : (
              verificationItems.map((item) => (
                <div key={item.id} className="rounded-lg border border-white/10 bg-white/5 p-2">
                  <p className="text-xs">{item.message}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-1">
                    {item.author} • {new Date(item.createdAt).toLocaleTimeString()}
                  </p>
                  <p className="text-[10px] uppercase tracking-wide mt-1 text-primary">
                    {item.answered
                      ? `Answered by ${(item.responses ?? []).length}/${(item.requiredResponders ?? []).length || (item.responses ?? []).length}`
                      : `Pending: ${(item.pendingResponders ?? []).join(", ") || "waiting"}`}
                  </p>
                  {item.stale ? (
                    <p className="text-[10px] uppercase tracking-wide mt-1 text-amber-300">
                      SLA exceeded{item.escalatedAt ? ` • escalated ${new Date(item.escalatedAt).toLocaleTimeString()}` : ""}
                    </p>
                  ) : null}
                  <div className="mt-1 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => runVerificationAction(item.id, "refresh-context")}
                      disabled={verificationActionBusy !== null}
                      className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-cyan-200 disabled:opacity-40"
                    >
                      Refresh Context
                    </button>
                    <button
                      type="button"
                      onClick={() => runVerificationAction(item.id, "escalate")}
                      disabled={verificationActionBusy !== null}
                      className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-amber-200 disabled:opacity-40"
                    >
                      Escalate Now
                    </button>
                  </div>
                  {(item.responses ?? []).slice(0, 3).map((response, index) => (
                    <div key={response.id ?? index} className="mt-1 rounded border border-white/10 bg-black/20 p-2">
                      <p className="text-[11px] text-white/80">{response.message}</p>
                      <div className="mt-1 flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => sendResponseFeedback(item.id, response.id, index, "useful")}
                          disabled={feedbackBusy !== null}
                          className="rounded border border-green-500/30 bg-green-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-green-200 disabled:opacity-40"
                        >
                          Useful ({response.feedback?.useful ?? 0})
                        </button>
                        <button
                          type="button"
                          onClick={() => sendResponseFeedback(item.id, response.id, index, "notUseful")}
                          disabled={feedbackBusy !== null}
                          className="rounded border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-red-200 disabled:opacity-40"
                        >
                          Not Useful ({response.feedback?.notUseful ?? 0})
                        </button>
                      </div>
                    </div>
                  ))}
                  {Array.isArray(item.researchContext) && item.researchContext.length > 0 ? (
                    <div className="mt-2 rounded-md border border-cyan-400/20 bg-cyan-400/5 p-2 space-y-1">
                      <p className="text-[10px] uppercase tracking-wide text-cyan-300">Memory Context</p>
                      {item.researchContext.slice(0, 2).map((hit) => (
                        <p key={hit.id} className="text-[11px] text-cyan-100/90">
                          {hit.sourceAgent} ({Math.round(Math.max(0, Math.min(1, hit.confidence || 0)) * 100)}% •{" "}
                          {hit.createdAt ? new Date(hit.createdAt).toLocaleTimeString() : "n/a"}): {hit.summary}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
          <textarea
            value={verificationDraft}
            onChange={(event) => setVerificationDraft(event.target.value)}
            placeholder="Question to verify: what should be checked?"
            className="w-full rounded-lg border border-white/10 bg-black/30 p-2 text-xs min-h-[72px]"
          />
          <button
            onClick={() => submitBoardItem("verification")}
            disabled={boardBusy !== null}
            className="w-full px-3 py-2 rounded-lg border border-primary/30 bg-primary/10 text-xs font-bold uppercase tracking-wider disabled:opacity-40"
          >
            {boardBusy === "verification" ? <Loader2 className="w-4 h-4 animate-spin inline" /> : null} Post Verification Request
          </button>
        </section>

        <section className="glass-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Ideas & Comments</h2>
            <MessageSquarePlus className="w-4 h-4 text-primary" />
          </div>
          <div className="space-y-2 max-h-56 overflow-auto pr-1">
            {ideaItems.length === 0 ? (
              <p className="text-xs text-muted-foreground">No ideas posted yet.</p>
            ) : (
              ideaItems.map((item) => (
                <div key={item.id} className="rounded-lg border border-white/10 bg-white/5 p-2">
                  <p className="text-xs">{item.message}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-1">
                    {item.author} • {new Date(item.createdAt).toLocaleTimeString()}
                  </p>
                </div>
              ))
            )}
          </div>
          <textarea
            value={ideaDraft}
            onChange={(event) => setIdeaDraft(event.target.value)}
            placeholder="Idea to improve reliability, quality, or speed..."
            className="w-full rounded-lg border border-white/10 bg-black/30 p-2 text-xs min-h-[72px]"
          />
          <button
            onClick={() => submitBoardItem("idea")}
            disabled={boardBusy !== null}
            className="w-full px-3 py-2 rounded-lg border border-primary/30 bg-primary/10 text-xs font-bold uppercase tracking-wider disabled:opacity-40"
          >
            {boardBusy === "idea" ? <Loader2 className="w-4 h-4 animate-spin inline" /> : null} Post Idea
          </button>
        </section>

        <section className="glass-card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-primary">Agent Builder</h2>
            <Hammer className="w-4 h-4 text-primary" />
          </div>
          <input
            value={factoryGoal}
            onChange={(event) => setFactoryGoal(event.target.value)}
            placeholder="Tell AgentForge what to build (e.g. UI + security + analytics)"
            className="w-full rounded-lg border border-white/10 bg-black/30 p-2 text-xs"
          />
          <button
            onClick={runAgentFactory}
            disabled={factoryBusy}
            className="w-full px-3 py-2 rounded-lg border border-white/20 bg-white/10 text-xs font-bold uppercase tracking-wider disabled:opacity-40"
          >
            {factoryBusy ? <Loader2 className="w-4 h-4 animate-spin inline" /> : <Zap className="w-4 h-4 inline" />} Build Agents
          </button>
          {factoryReport ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                  <p className="text-[10px] uppercase text-muted-foreground">Overall</p>
                  <p className="text-sm font-bold">{factoryReport.scores?.overall ?? 0}%</p>
                </div>
                <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                  <p className="text-[10px] uppercase text-muted-foreground">Completion</p>
                  <p className="text-sm font-bold">{factoryReport.scores?.completion ?? 0}%</p>
                </div>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                <p className="text-[10px] uppercase text-muted-foreground">Goal Alignment</p>
                <p className="text-sm font-bold">{factoryReport.scores?.goal_alignment ?? 0}%</p>
              </div>
              <p className="text-[10px] uppercase text-muted-foreground">Goal: {factoryReport.requested?.goal ?? "default optimization pack"}</p>
              <p className="text-[10px] uppercase text-muted-foreground">
                Built: {(factoryReport.delivered?.created_agents ?? []).join(", ") || "n/a"}
              </p>
              <div className="space-y-1">
                {(factoryReport.feedback ?? []).slice(0, 3).map((line, idx) => (
                  <p key={idx} className="text-xs text-white/85">
                    {line}
                  </p>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Run the factory to create and evaluate optimization agents.</p>
          )}
        </section>
      </div>

      <div className="grid grid-cols-12 gap-8">
        <div className="col-span-12 lg:col-span-8 space-y-12">
          <section className="glass-card border-white/5 bg-white/[0.02]">
            <h2 className="text-xs font-bold mb-4 uppercase tracking-[0.2em] text-primary">Role Excellence</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {roleLeaders.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                  <div className="flex flex-col">
                    <span className="text-[9px] text-muted-foreground uppercase tracking-wider font-bold">{item.role}</span>
                    <span className="text-sm font-semibold">{item.leader.name}</span>
                  </div>
                  <span className="text-xs font-mono text-primary font-bold">{(item.leader.fitness || 0).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="flex justify-between items-end mb-6 border-b border-white/5 pb-4">
              <h2 className="text-xl font-bold px-2 uppercase tracking-[0.3em] text-[10px] text-white">Swarm Pulse Delta</h2>
              <span className="text-[10px] text-muted-foreground uppercase h-fit font-mono">Live Sync | Top 10 Operational</span>
            </div>
            <AgentPulse agents={top10Agents} activityByAgent={agentActivity} />
          </section>

          <section>
            <h2 className="text-xl font-bold mb-4 px-2 uppercase tracking-widest text-[10px] text-white">Infrastructure Resources</h2>
            <ResourceMonitor resources={data.resources || []} />
          </section>
        </div>

        <div className="col-span-12 lg:col-span-4 h-full">
          <section className="h-full">
            <h2 className="text-xl font-bold mb-4 px-2 uppercase tracking-widest text-[10px] text-white">Cognitive Neural Stream</h2>
            <CognitiveFeed feed={data.feed || []} />
          </section>
        </div>
      </div>
    </>
  );
}
