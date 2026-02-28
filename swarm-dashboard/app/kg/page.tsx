"use client";

import { useEffect, useState } from "react";
import { ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

type Node = { id: string; label: string; x: number; y: number; type: "agent" | "role" | "event"; score?: number };

export default function KnowledgeGraphPage() {
  const [limit, setLimit] = useState(24);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [summary, setSummary] = useState<{ totalNodes: number; visibleNodes: number; totalEdges: number; visibleEdges: number } | null>(null);

  const fetchGraph = async (n: number) => {
    try {
      const res = await fetch(`/api/knowledge-graph?limit=${n}`, { cache: "no-store" });
      if (!res.ok) return;
      const json = await res.json();
      setNodes(Array.isArray(json?.nodes) ? json.nodes : []);
      setSummary(json?.summary ?? null);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchGraph(limit);
    const interval = setInterval(() => fetchGraph(limit), 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchGraph(limit);
  }, [limit]);

  const points = nodes.map((node) => ({ x: node.x, y: node.y, z: node.type === "agent" ? 220 : node.type === "role" ? 170 : 120 }));

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">Knowledge Graph</h1>
        <p className="text-muted-foreground text-sm font-mono opacity-60">Live graph of agents, roles, and recent telemetry events.</p>
      </header>

      <section className="glass-card space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-[0.2em] text-primary font-bold">Node Visibility</p>
          <p className="text-[10px] uppercase text-muted-foreground">{summary?.visibleNodes ?? 0} / {summary?.totalNodes ?? 0}</p>
        </div>
        <input type="range" min={5} max={60} value={limit} onChange={(e) => setLimit(Number(e.target.value))} className="w-full" />
        <div className="h-[420px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <XAxis dataKey="x" type="number" domain={[0, 100]} hide />
              <YAxis dataKey="y" type="number" domain={[0, 100]} hide />
              <Tooltip />
              <Scatter data={points} fill="#60a5fa" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
