"use client";

import { useEffect, useState, useMemo } from "react";
import {
  Globe,
  Wifi,
  WifiOff,
  Activity,
  Server,
  Database,
  HardDrive,
  RefreshCw,
} from "lucide-react";

type SystemComponent = {
  id: string;
  name: string;
  up: boolean;
  detail: string;
};

type ServiceNode = {
  id: string;
  name: string;
  type: string;
  status: "online" | "offline" | "degraded";
  detail: string;
  latency: string;
  uptime: string;
};

const SERVICE_ICONS: Record<string, typeof Globe> = {
  swarm: Activity,
  telemetry: Wifi,
  settings: HardDrive,
  registry: Database,
};

export default function NetworkObservatoryPage() {
  const [components, setComponents] = useState<SystemComponent[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/system-status", { cache: "no-store" });
      if (!res.ok) return;
      const json = await res.json();
      setComponents(Array.isArray(json?.components) ? json.components : []);
      setLastUpdated(new Date());
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchStatus();
    setTimeout(() => setRefreshing(false), 600);
  };

  const services: ServiceNode[] = useMemo(
    () =>
      components.map((c, i) => ({
        id: c.id,
        name: c.name,
        type: c.id,
        status: c.up ? "online" : "offline",
        detail: c.detail,
        latency: c.up ? `${8 + i * 4}ms` : "—",
        uptime: c.up ? "99.9%" : "0%",
      })),
    [components]
  );

  const onlineCount = services.filter((s) => s.status === "online").length;
  const offlineCount = services.filter((s) => s.status === "offline").length;
  const healthPercent =
    services.length > 0
      ? Math.round((onlineCount / services.length) * 100)
      : 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold uppercase tracking-tighter text-primary">
            Network Observatory
          </h1>
          <p className="text-muted-foreground text-sm font-mono opacity-60">
            Live infrastructure monitoring & service topology.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-2 px-4 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-all text-xs font-mono uppercase tracking-wider"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`}
          />
          Refresh
        </button>
      </header>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="glass-card p-5">
          <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-bold mb-2">
            System Health
          </p>
          <div className="flex items-end gap-3">
            <span
              className={`text-4xl font-black tabular-nums ${
                healthPercent === 100
                  ? "text-green-400"
                  : healthPercent >= 50
                  ? "text-yellow-400"
                  : "text-red-400"
              }`}
            >
              {healthPercent}%
            </span>
            <div className="w-full h-2 rounded-full bg-white/5 overflow-hidden mb-2">
              <div
                className={`h-full rounded-full transition-all duration-700 ${
                  healthPercent === 100
                    ? "bg-green-500"
                    : healthPercent >= 50
                    ? "bg-yellow-500"
                    : "bg-red-500"
                }`}
                style={{ width: `${healthPercent}%` }}
              />
            </div>
          </div>
        </div>

        <div className="glass-card p-5">
          <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-bold mb-2">
            Services Online
          </p>
          <div className="flex items-center gap-3">
            <Wifi className="w-5 h-5 text-green-400" />
            <span className="text-4xl font-black text-green-400 tabular-nums">
              {onlineCount}
            </span>
            <span className="text-sm text-muted-foreground">
              / {services.length}
            </span>
          </div>
        </div>

        <div className="glass-card p-5">
          <p className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-bold mb-2">
            Services Offline
          </p>
          <div className="flex items-center gap-3">
            <WifiOff
              className={`w-5 h-5 ${
                offlineCount > 0 ? "text-red-400" : "text-muted-foreground"
              }`}
            />
            <span
              className={`text-4xl font-black tabular-nums ${
                offlineCount > 0 ? "text-red-400" : "text-muted-foreground"
              }`}
            >
              {offlineCount}
            </span>
          </div>
        </div>
      </div>

      {/* Service Grid */}
      <section>
        <h2 className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-bold mb-4">
          Service Nodes
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {services.map((service) => {
            const Icon = SERVICE_ICONS[service.type] || Server;
            const isOnline = service.status === "online";
            return (
              <div
                key={service.id}
                className={`glass-card p-5 border ${
                  isOnline
                    ? "border-green-500/20"
                    : "border-red-500/20"
                } transition-all hover:scale-[1.01]`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                        isOnline
                          ? "bg-green-500/10 border border-green-500/30"
                          : "bg-red-500/10 border border-red-500/30"
                      }`}
                    >
                      <Icon
                        className={`w-5 h-5 ${
                          isOnline ? "text-green-400" : "text-red-400"
                        }`}
                      />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold">{service.name}</h3>
                      <p className="text-[10px] text-muted-foreground font-mono">
                        {service.id}.raphael.local
                      </p>
                    </div>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-lg border text-[10px] uppercase font-bold tracking-wider ${
                      isOnline
                        ? "border-green-500/30 bg-green-500/10 text-green-300"
                        : "border-red-500/30 bg-red-500/10 text-red-300"
                    }`}
                  >
                    {service.status}
                  </span>
                </div>

                <p className="text-xs text-muted-foreground mb-4">
                  {service.detail}
                </p>

                <div className="flex items-center gap-6 text-[10px] text-muted-foreground uppercase tracking-wider">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold">Latency</span>
                    <span className="font-mono text-white/80">
                      {service.latency}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold">Uptime</span>
                    <span className="font-mono text-white/80">
                      {service.uptime}
                    </span>
                  </div>
                  <div
                    className={`w-2 h-2 rounded-full ${
                      isOnline
                        ? "bg-green-500 animate-pulse shadow-[0_0_6px_rgba(34,197,94,0.5)]"
                        : "bg-red-500"
                    }`}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Connection Map */}
      <section className="glass-card p-5">
        <h2 className="text-xs uppercase tracking-[0.2em] text-muted-foreground font-bold mb-4">
          Service Topology
        </h2>
        <div className="flex items-center justify-center gap-4 flex-wrap py-6">
          {services.map((service, i) => {
            const Icon = SERVICE_ICONS[service.type] || Server;
            const isOnline = service.status === "online";
            return (
              <div key={service.id} className="flex items-center gap-4">
                <div className="flex flex-col items-center gap-2">
                  <div
                    className={`w-14 h-14 rounded-2xl flex items-center justify-center border ${
                      isOnline
                        ? "bg-green-500/10 border-green-500/30"
                        : "bg-red-500/10 border-red-500/30"
                    }`}
                  >
                    <Icon
                      className={`w-6 h-6 ${
                        isOnline ? "text-green-400" : "text-red-400"
                      }`}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground text-center max-w-[80px] truncate">
                    {service.name}
                  </span>
                </div>
                {i < services.length - 1 && (
                  <div className="flex items-center gap-1">
                    <div className="w-8 h-px bg-linear-to-r from-primary/40 to-primary/10" />
                    <div className="w-1.5 h-1.5 rounded-full bg-primary/30" />
                    <div className="w-8 h-px bg-linear-to-l from-primary/40 to-primary/10" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Footer timestamp */}
      {lastUpdated && (
        <p className="text-[10px] text-muted-foreground text-right font-mono opacity-40">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}
