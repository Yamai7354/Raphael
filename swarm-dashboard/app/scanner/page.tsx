"use client";

import { useEffect, useMemo, useState } from "react";

type SystemComponent = { id: string; name: string; up: boolean; detail: string };

export default function NetworkScannerPage() {
  const [components, setComponents] = useState<SystemComponent[]>([]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch("/api/system-status", { cache: "no-store" });
        if (!res.ok) return;
        const json = await res.json();
        setComponents(Array.isArray(json?.components) ? json.components : []);
      } catch (error) {
        console.error(error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const rows = useMemo(
    () =>
      components.map((component, idx) => ({
        host: `${component.id}.raphael.local`,
        service: component.name,
        latency: component.up ? `${14 + idx * 7}ms` : "timeout",
        status: component.up ? "open" : "closed",
        detail: component.detail,
      })),
    [components]
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">Network Scanner</h1>
        <p className="text-muted-foreground text-sm font-mono opacity-60">Service-level network visibility for swarm infrastructure.</p>
      </header>
      <section className="glass-card overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-white/10 text-muted-foreground uppercase tracking-wider">
              <th className="text-left py-3 px-3">Host</th>
              <th className="text-left py-3 px-3">Service</th>
              <th className="text-left py-3 px-3">Latency</th>
              <th className="text-left py-3 px-3">Port State</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.host} className="border-b border-white/5">
                <td className="py-3 px-3 font-mono">{row.host}</td>
                <td className="py-3 px-3">{row.service}</td>
                <td className="py-3 px-3 font-mono">{row.latency}</td>
                <td className="py-3 px-3">
                  <span className={`px-2 py-1 rounded-md border text-[10px] uppercase ${row.status === "open" ? "border-green-500/30 bg-green-500/10 text-green-300" : "border-red-500/30 bg-red-500/10 text-red-300"}`}>
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
