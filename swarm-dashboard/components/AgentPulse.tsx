"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { User, Award, TrendingUp, Zap, ChevronRight, Loader2, BriefcaseBusiness, BarChart3 } from "lucide-react";

interface Agent {
  name: string;
  role: string;
  status: string;
  model: string | null;
  fitness?: number;
  globalRank?: number;
  task_success_rate?: number;
}

type AgentActivity = {
  currentJob: string;
  successRate: number;
  jobsCompleted: number;
  recentJobs: Array<{ summary: string; success: boolean | null; time?: string }>;
};

export const AgentPulse = ({ agents, activityByAgent = {} }: { agents: Agent[]; activityByAgent?: Record<string, AgentActivity> }) => {
  const [triggering, setTriggering] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const handleTrigger = async (agentName: string) => {
    setTriggering(agentName);
    try {
      const res = await fetch("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "start", agentName }),
      });
      if (!res.ok) throw new Error("Failed to trigger");
    } catch (err) {
      console.error(err);
    } finally {
      setTriggering(null);
    }
  };

  const cardAgents = useMemo(
    () =>
      agents.map((agent) => ({
        ...agent,
        activity: activityByAgent[agent.name.trim()] ?? activityByAgent[agent.name],
      })),
    [agents, activityByAgent]
  );

  if (agents.length === 0) {
    return (
      <div className="glass-card text-center py-16 border-white/10">
        <p className="text-sm uppercase tracking-widest font-black opacity-70">Awaiting Agent Telemetry</p>
        <p className="text-xs text-muted-foreground mt-2">Run the swarm exporter to populate live cards.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6">
      {cardAgents.map((agent) => {
        const isExpanded = expanded === agent.name;
        const displaySuccessRate =
          agent.activity?.successRate ??
          (typeof agent.task_success_rate === "number" ? agent.task_success_rate : null);
        return (
          <div
            key={agent.name}
            onClick={() => setExpanded((current) => (current === agent.name ? null : agent.name))}
            className="glass-card flex flex-col gap-4 relative overflow-hidden group hover:border-primary/30 transition-all duration-500 cursor-pointer"
          >
            <div className="absolute -top-4 -right-4 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity">
              <span className="text-8xl font-black italic">{agent.globalRank || "#"}</span>
            </div>

            <div className="flex items-center gap-3 relative z-10">
              <div
                className={`p-2.5 rounded-xl border ${
                  agent.status === "Executing"
                    ? "bg-primary/20 border-primary/40 text-primary animate-pulse"
                    : "bg-white/5 border-white/10 text-muted-foreground"
                }`}
              >
                <User className="w-5 h-5" />
              </div>
              <div className="flex-1 overflow-hidden">
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-lg truncate">{agent.name}</h3>
                  {agent.globalRank && agent.globalRank <= 3 && (
                    <Award
                      className={`w-4 h-4 ${
                        agent.globalRank === 1 ? "text-yellow-500" : agent.globalRank === 2 ? "text-zinc-400" : "text-amber-600"
                      }`}
                    />
                  )}
                </div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold truncate">{agent.role}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 py-2 relative z-10">
              <div className="p-2 rounded-lg bg-black/40 border border-white/5">
                <p className="text-[8px] text-muted-foreground uppercase tracking-tighter">Fitness</p>
                <div className="flex items-center gap-1.5">
                  <TrendingUp className="w-3 h-3 text-primary" />
                  <span className="text-sm font-mono font-bold">{(agent.fitness || 0).toFixed(1)}%</span>
                </div>
              </div>
              <div className="p-2 rounded-lg bg-black/40 border border-white/5">
                <p className="text-[8px] text-muted-foreground uppercase tracking-tighter">Ranking</p>
                <span className="text-sm font-bold">#{agent.globalRank || "---"} Global</span>
              </div>
            </div>

            <div className="flex justify-between items-end mt-2 relative z-10 border-t border-white/5 pt-3">
              <div className="space-y-1">
                <p className="text-[9px] text-muted-foreground uppercase tracking-widest font-black">Active Model</p>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500/50" />
                  <p className="text-xs font-medium opacity-80">{agent.model || "DEEPSEEK_v3"}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10">
                <div
                  className={`w-2 h-2 rounded-full ${
                    agent.status === "Idle" ? "bg-zinc-500" : "bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]"
                  }`}
                />
                <span className="text-[10px] font-black uppercase">{agent.status}</span>
              </div>
            </div>

            {isExpanded && (
              <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 relative z-10">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] uppercase tracking-wider font-bold text-primary">Current Activity</span>
                  <span className="text-[10px] text-muted-foreground">click card to collapse</span>
                </div>
                <p className="text-xs mt-2 text-white/90">{agent.activity?.currentJob ?? `${agent.role} telemetry synchronization`}</p>
                <div className="grid grid-cols-2 gap-2 mt-3">
                  <div className="rounded-md border border-white/10 bg-black/30 p-2">
                    <p className="text-[9px] text-muted-foreground uppercase">Success Rate</p>
                    <p className="text-sm font-bold flex items-center gap-1">
                      <BarChart3 className="w-3 h-3 text-primary" />
                      {displaySuccessRate !== null ? `${displaySuccessRate.toFixed(1)}%` : "N/A"}
                    </p>
                  </div>
                  <div className="rounded-md border border-white/10 bg-black/30 p-2">
                    <p className="text-[9px] text-muted-foreground uppercase">Jobs Completed</p>
                    <p className="text-sm font-bold flex items-center gap-1">
                      <BriefcaseBusiness className="w-3 h-3 text-primary" />
                      {agent.activity?.jobsCompleted ?? 0}
                    </p>
                  </div>
                </div>
                <div className="mt-3 space-y-1">
                  {(agent.activity?.recentJobs ?? []).slice(0, 3).map((job, idx) => (
                    <p key={idx} className="text-[11px] text-white/80">
                      • {job.summary} {job.success === null ? "" : job.success ? "(success)" : "(failed)"}
                    </p>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2 pt-2 border-t border-white/5 relative z-10" onClick={(event) => event.stopPropagation()}>
              <button
                disabled={triggering === agent.name}
                onClick={() => handleTrigger(agent.name)}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-[10px] font-bold uppercase tracking-widest transition-colors disabled:opacity-50"
              >
                {triggering === agent.name ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                Trigger Task
              </button>
              <Link href={`/agents/${agent.name}`} className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white transition-colors">
                <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        );
      })}
    </div>
  );
};
