"use client";

import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Job = {
  name: string;
  role: string;
  status: string;
  currentJob: string;
  projection: Array<{ step: number; projectedFitness: number }>;
};

export default function BrainPage() {
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch("/api/agent-jobs", { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        setJobs(Array.isArray(json?.jobs) ? json.jobs : []);
      } catch (error) {
        console.error(error);
      }
    };

    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  const focus = jobs[0] ?? null;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">Neural Brain</h1>
        <p className="text-muted-foreground text-sm font-mono opacity-60">Collective cognitive load and agent projection curves.</p>
      </header>

      <section className="glass-card space-y-4">
        {focus ? (
          <>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4">
              <p className="text-sm font-bold">{focus.name}</p>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{focus.role} · {focus.status}</p>
              <p className="text-xs mt-2 text-white/80">{focus.currentJob}</p>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={focus.projection}>
                  <XAxis dataKey="step" stroke="#666" fontSize={10} />
                  <YAxis stroke="#666" fontSize={10} />
                  <Tooltip />
                  <Line dataKey="projectedFitness" stroke="#22c55e" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No active brain telemetry yet.</p>
        )}
      </section>
    </div>
  );
}
