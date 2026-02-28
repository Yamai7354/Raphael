"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";

type ModelSyncReport = {
  model_count?: number;
  usable_model_count?: number;
  assignments?: Record<string, string>;
  task_assignments?: Record<string, string>;
};

export default function ModelsPage() {
  const [routing, setRouting] = useState("hybrid");
  const [models, setModels] = useState<string[]>([]);
  const [defaultModel, setDefaultModel] = useState("");
  const [busy, setBusy] = useState<null | "sync" | "refresh">(null);
  const [report, setReport] = useState<ModelSyncReport | null>(null);

  const fetchModels = async () => {
    setBusy("refresh");
    try {
      const res = await fetch("/api/models", { cache: "no-store" });
      const json = await res.json();
      const list = Array.isArray(json?.models) ? json.models : [];
      setModels(list);
      if (!defaultModel && list.length > 0) {
        setDefaultModel(list[0]);
      }
      setReport((json?.report as ModelSyncReport) ?? null);
    } catch (error) {
      console.error(error);
    } finally {
      setBusy(null);
    }
  };

  const syncModels = async () => {
    setBusy("sync");
    try {
      const res = await fetch("/api/models", { method: "POST" });
      const json = await res.json();
      setReport(json);
      await fetchModels();
    } catch (error) {
      console.error(error);
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const assignedCount = useMemo(() => Object.keys(report?.assignments ?? {}).length, [report]);

  return (
    <div className="space-y-8">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">Models</h1>
          <p className="text-muted-foreground text-sm font-mono opacity-60">Model routing and fallback policy controls.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchModels}
            disabled={busy !== null}
            className="px-3 py-2 rounded-lg border border-white/20 bg-white/10 text-xs font-bold uppercase"
          >
            {busy === "refresh" ? <Loader2 className="w-4 h-4 animate-spin inline" /> : <RefreshCw className="w-4 h-4 inline" />} Refresh
          </button>
          <button
            onClick={syncModels}
            disabled={busy !== null}
            className="px-3 py-2 rounded-lg border border-primary/30 bg-primary/10 text-xs font-bold uppercase text-primary"
          >
            {busy === "sync" ? <Loader2 className="w-4 h-4 animate-spin inline" /> : null} Sync to Agents
          </button>
        </div>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card space-y-4">
          <h2 className="text-xs uppercase tracking-[0.2em] text-primary font-bold">Routing Mode</h2>
          <div className="grid grid-cols-3 gap-2">
            {["local", "hybrid", "cloud"].map((mode) => (
              <button
                key={mode}
                onClick={() => setRouting(mode)}
                className={`rounded-lg border px-3 py-3 text-xs uppercase font-bold ${
                  routing === mode ? "border-primary/40 bg-primary/15 text-primary" : "border-white/10 bg-white/5"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">Installed models detected: {models.length}</p>
          <p className="text-xs text-muted-foreground">Assigned agents: {assignedCount}</p>
        </div>

        <div className="glass-card space-y-4">
          <h2 className="text-xs uppercase tracking-[0.2em] text-primary font-bold">Default Model</h2>
          <select
            value={defaultModel}
            onChange={(e) => setDefaultModel(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm"
          >
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted-foreground">Use “Sync to Agents” to rebalance model assignments by role.</p>
        </div>
      </section>

      <section className="glass-card space-y-3">
        <h2 className="text-xs uppercase tracking-[0.2em] text-primary font-bold">Available Models</h2>
        <div className="max-h-80 overflow-auto pr-1 space-y-1">
          {models.map((model) => (
            <div key={model} className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-xs font-mono">
              {model}
            </div>
          ))}
          {models.length === 0 && <p className="text-xs text-muted-foreground">No models detected.</p>}
        </div>
      </section>
      <section className="glass-card space-y-3">
        <h2 className="text-xs uppercase tracking-[0.2em] text-primary font-bold">Task Routing</h2>
        <div className="space-y-1">
          {Object.entries(report?.task_assignments ?? {}).map(([task, model]) => (
            <div key={task} className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-xs">
              <span className="uppercase tracking-wide text-muted-foreground">{task}</span>
              <span className="ml-2 font-mono">{model}</span>
            </div>
          ))}
          {Object.keys(report?.task_assignments ?? {}).length === 0 ? (
            <p className="text-xs text-muted-foreground">Run sync to generate task routing assignments.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
