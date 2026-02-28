"use client";

import { useEffect, useMemo, useState } from "react";
import { AgentPulse } from "@/components/AgentPulse";
import { Users, Search, Play, Loader2, RefreshCw } from "lucide-react";

type Agent = {
  name: string;
  role: string;
  status: string;
  model: string | null;
  fitness?: number;
  task_success_rate?: number;
  culture?: string;
};
type AgentActivity = {
  currentJob: string;
  successRate: number;
  jobsCompleted: number;
  recentJobs: Array<{ summary: string; success: boolean | null; time?: string }>;
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activity, setActivity] = useState<Record<string, AgentActivity>>({});
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<null | "start-all" | "refresh">(null);

  const fetchAgents = async () => {
    try {
      const res = await fetch("/api/agents", { cache: "no-store" });
      if (!res.ok) throw new Error(`Failed agents fetch: ${res.status}`);
      const json = await res.json();
      setAgents(Array.isArray(json?.agents) ? json.agents : []);
    } catch (error) {
      console.error(error);
      setAgents([]);
    }
  };

  const fetchActivity = async () => {
    try {
      const res = await fetch("/api/agent-activity", { cache: "no-store" });
      if (!res.ok) return;
      const json = await res.json();
      setActivity(json?.activity ?? {});
    } catch (error) {
      console.error(error);
    }
  };

  const startAllAgents = async () => {
    setBusy("start-all");
    try {
      await fetch("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "start-all" }),
      });
      await fetchAgents();
    } catch (error) {
      console.error(error);
    } finally {
      setBusy(null);
    }
  };

  const refreshNow = async () => {
    setBusy("refresh");
    await Promise.all([fetchAgents(), fetchActivity()]);
    setBusy(null);
  };

  useEffect(() => {
    fetchAgents();
    fetchActivity();
    const interval = setInterval(() => {
      fetchAgents();
      fetchActivity();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredAgents = useMemo(() => {
      // Deduplicate by name, keeping the entry with the highest fitness
      const deduped = new Map<string, Agent>();
      for (const agent of agents) {
        const name = agent.name.trim();
        const existing = deduped.get(name);
        if (!existing || (agent.fitness || 0) > (existing.fitness || 0)) {
          deduped.set(name, { ...agent, name });
        }
      }
      return Array.from(deduped.values())
        .filter(
          (agent) =>
            agent.name.toLowerCase().includes(search.toLowerCase()) ||
            agent.role.toLowerCase().includes(search.toLowerCase())
        )
        .sort((a, b) => (b.fitness || 0) - (a.fitness || 0))
        .map((agent, idx) => ({ ...agent, globalRank: idx + 1 }));
    }, [agents, search]);

  return (
    <>
      <header className="flex flex-col gap-4 mb-12 xl:flex-row xl:justify-between xl:items-end">
        <div>
          <h1 className="text-3xl font-black premium-gradient-text uppercase tracking-tighter">Agent Personnel</h1>
          <p className="text-xs text-muted-foreground uppercase tracking-widest font-bold opacity-60">
            Complete Swarm Directory
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="SEARCH AGENTS..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-xs font-bold focus:outline-none focus:border-primary/50 transition-all w-72"
            />
          </div>
          <button
            onClick={refreshNow}
            disabled={busy !== null}
            className="px-4 py-3 rounded-xl border border-white/20 bg-white/10 text-xs font-bold uppercase tracking-wider disabled:opacity-40"
          >
            {busy === "refresh" ? <Loader2 className="w-4 h-4 animate-spin inline" /> : <RefreshCw className="w-4 h-4 inline" />} Refresh
          </button>
          <button
            onClick={startAllAgents}
            disabled={busy !== null || agents.length === 0}
            className="px-4 py-3 rounded-xl border border-primary/30 bg-primary/10 text-primary text-xs font-bold uppercase tracking-wider disabled:opacity-40"
          >
            {busy === "start-all" ? <Loader2 className="w-4 h-4 animate-spin inline" /> : <Play className="w-4 h-4 inline" />} Start All
          </button>
        </div>
      </header>

      <section className="space-y-6">
        <div className="flex items-center justify-between border-b border-white/5 pb-4">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-primary" />
            <span className="text-[10px] uppercase font-bold tracking-[0.2em] text-white">
              Registered Agents ({filteredAgents.length})
            </span>
          </div>
        </div>

        <AgentPulse agents={filteredAgents} activityByAgent={activity} />
      </section>
    </>
  );
}
