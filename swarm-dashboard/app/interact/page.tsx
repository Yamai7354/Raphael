"use client";

import { useEffect, useState } from "react";

type Agent = { name: string; role: string; status?: string };

export default function InteractPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState("");
  const [logs, setLogs] = useState<string[]>(["Terminal initialized."]);
  const [busy, setBusy] = useState(false);

  const fetchAgents = async () => {
    try {
      const res = await fetch("/api/agents", { cache: "no-store" });
      if (!res.ok) return;
      const json = await res.json();
      const list = Array.isArray(json?.agents) ? json.agents : [];
      setAgents(list);
      if (!selected && list.length > 0) setSelected(list[0].name);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const runCommand = async (action: "start" | "start-all") => {
    setBusy(true);
    try {
      const body = action === "start" ? { action, agentName: selected } : { action };
      const res = await fetch("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = await res.json();
      setLogs((prev) => [`> ${json?.message ?? "Command complete"}`, ...prev].slice(0, 24));
      await fetchAgents();
    } catch (error) {
      console.error(error);
      setLogs((prev) => ["> Command failed", ...prev].slice(0, 24));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">Direct Interaction</h1>
        <p className="text-muted-foreground text-sm font-mono opacity-60">Manual command lane for triggering active agents.</p>
      </header>

      <div className="glass-card space-y-4">
        <div className="flex flex-wrap gap-2">
          <select value={selected} onChange={(e) => setSelected(e.target.value)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm min-w-[220px]">
            {agents.map((agent) => (
              <option key={agent.name} value={agent.name}>{agent.name} · {agent.role}</option>
            ))}
          </select>
          <button disabled={busy || !selected} onClick={() => runCommand("start")} className="px-4 py-2 rounded-xl border border-primary/30 bg-primary/10 text-primary text-xs font-bold uppercase disabled:opacity-40">Start Agent</button>
          <button disabled={busy || agents.length === 0} onClick={() => runCommand("start-all")} className="px-4 py-2 rounded-xl border border-white/20 bg-white/10 text-xs font-bold uppercase disabled:opacity-40">Start All</button>
        </div>

        <div className="rounded-xl border border-white/10 bg-black/40 p-4 max-h-[360px] overflow-y-auto font-mono text-xs space-y-2">
          {logs.map((line, idx) => (
            <p key={idx} className="text-white/80">{line}</p>
          ))}
        </div>
      </div>
    </div>
  );
}
