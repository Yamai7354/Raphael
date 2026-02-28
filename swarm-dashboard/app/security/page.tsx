"use client";

import { useEffect, useState } from "react";

type SystemComponent = { id: string; name: string; up: boolean; detail: string };

export default function SecurityPage() {
  const [components, setComponents] = useState<SystemComponent[]>([]);
  const [loading, setLoading] = useState<Record<string, boolean>>({});

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

  const resetComponent = async (id: string) => {
    setLoading((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await fetch("/api/system-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ componentId: id }),
      });
      if (res.ok) {
        const json = await res.json();
        setComponents(Array.isArray(json?.components) ? json.components : []);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">Security Audit</h1>
        <p className="text-muted-foreground text-sm font-mono opacity-60">Runtime health checks with one-click reset actions.</p>
      </header>
      <section className="glass-card space-y-4">
        {components.map((component) => {
          const isLoading = Boolean(loading[component.id]);
          return (
            <button
              key={component.id}
              onClick={() => resetComponent(component.id)}
              className={`w-full rounded-xl border p-4 text-left ${
                isLoading ? "border-yellow-500/40 bg-yellow-500/15" : component.up ? "border-green-500/30 bg-green-500/10" : "border-red-500/30 bg-red-500/10"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-[0.2em] font-bold">{component.name}</span>
                <span className="text-xs font-bold uppercase">{isLoading ? "Loading" : component.up ? "Up" : "Down"}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">{isLoading ? "Running reset..." : component.detail}</p>
            </button>
          );
        })}
      </section>
    </div>
  );
}
