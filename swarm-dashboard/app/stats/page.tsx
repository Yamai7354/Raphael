"use client";

import { useEffect, useState } from "react";
import { ResourceMonitor } from "@/components/ResourceMonitor";

type Analytics = {
  totalAgents: number;
  activeAgents: number;
  idleAgents: number;
  averageFitness: number;
  manualOverrides: number;
  cpu: number;
  ram: number;
  vram: number;
};

type StatsData = { resources: Array<{ name: string; cpu: number; ram: number; vram: number }> };

export default function StatsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [stats, setStats] = useState<StatsData>({ resources: [] });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [aRes, sRes] = await Promise.all([
          fetch("/api/analytics", { cache: "no-store" }),
          fetch("/stats.json", { cache: "no-store" }),
        ]);

        if (aRes.ok) {
          const aJson = await aRes.json();
          setAnalytics(aJson?.metrics ?? null);
        }
        if (sRes.ok) {
          const sJson = await sRes.json();
          setStats({ resources: Array.isArray(sJson?.resources) ? sJson.resources : [] });
        }
      } catch (error) {
        console.error(error);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">Swarm Telemetry</h1>
        <p className="text-muted-foreground text-sm font-mono opacity-60">Deep dive into performance metrics and resource allocation.</p>
      </header>

      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card"><p className="text-[10px] uppercase text-muted-foreground">Total Agents</p><p className="text-2xl font-black">{analytics?.totalAgents ?? 0}</p></div>
        <div className="glass-card"><p className="text-[10px] uppercase text-muted-foreground">Active</p><p className="text-2xl font-black">{analytics?.activeAgents ?? 0}</p></div>
        <div className="glass-card"><p className="text-[10px] uppercase text-muted-foreground">Avg Fitness</p><p className="text-2xl font-black">{analytics?.averageFitness?.toFixed(1) ?? "0.0"}%</p></div>
        <div className="glass-card"><p className="text-[10px] uppercase text-muted-foreground">Overrides</p><p className="text-2xl font-black">{analytics?.manualOverrides ?? 0}</p></div>
      </section>

      <ResourceMonitor resources={stats.resources} />
    </div>
  );
}
