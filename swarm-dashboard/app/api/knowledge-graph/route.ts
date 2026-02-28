import { NextResponse } from "next/server";
import { readFile } from "node:fs/promises";
import path from "node:path";

type Agent = {
  name: string;
  role: string;
  fitness?: number;
};

type FeedItem = {
  summary?: string;
};

async function readStats(): Promise<{ agents: Agent[]; feed: FeedItem[] }> {
  try {
    const statsPath = path.join(process.cwd(), "public", "stats.json");
    const raw = await readFile(statsPath, "utf-8");
    const json = JSON.parse(raw) as { agents?: Agent[]; feed?: FeedItem[] };
    return {
      agents: Array.isArray(json.agents) ? json.agents : [],
      feed: Array.isArray(json.feed) ? json.feed : [],
    };
  } catch {
    return { agents: [], feed: [] };
  }
}

async function readRegistryAgents(): Promise<Agent[]> {
  try {
    const registryPath = path.join(process.cwd(), "data", "agents.json");
    const raw = await readFile(registryPath, "utf-8");
    const json = JSON.parse(raw) as { agents?: Agent[] };
    return Array.isArray(json.agents) ? json.agents : [];
  } catch {
    return [];
  }
}

type Neo4jNode = {
  id: string;
  label: string;
  type: "agent" | "role" | "event";
  x: number;
  y: number;
  score?: number;
};

type Neo4jEdge = { from: string; to: string };

function polarPosition(index: number, total: number, radius = 40) {
  const angle = (Math.PI * 2 * index) / Math.max(total, 1);
  return {
    x: 50 + radius * Math.cos(angle),
    y: 50 + radius * Math.sin(angle),
  };
}

async function readNeo4jGraph(limit: number): Promise<{
  nodes: Neo4jNode[];
  edges: Neo4jEdge[];
  source: "neo4j";
} | null> {
  const uri = process.env.NEO4J_URI || "bolt://127.0.0.1:7693";
  const user = process.env.NEO4J_USER || "neo4j";
  const password = process.env.NEO4J_PASSWORD || "";

  let driver: any = null;
  let session: any = null;
  try {
    // Lazy import so build doesn't fail if package is absent.
    const neo4jModule: any = await import("neo4j-driver").catch(() => null);
    if (!neo4jModule?.default) return null;

    const neo4j = neo4jModule.default;
    driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
    session = driver.session();

    const nodeResult = await session.run(
      `
      MATCH (n)
      RETURN
        elementId(n) AS id,
        labels(n) AS labels,
        coalesce(n.name, n.title, toString(elementId(n))) AS label,
        coalesce(toFloat(n.fitness), 0.0) AS score
      LIMIT $limit
      `,
      { limit: neo4j.int(limit) }
    );

    if (nodeResult.records.length === 0) {
      return { nodes: [], edges: [], source: "neo4j" };
    }

    const nodes: Neo4jNode[] = nodeResult.records.map((record: any, idx: number) => {
      const labels: string[] = record.get("labels") ?? [];
      const type: Neo4jNode["type"] = labels.includes("Agent")
        ? "agent"
        : labels.includes("Role")
          ? "role"
          : "event";
      const pos = polarPosition(idx, Math.max(nodeResult.records.length, 1), 38);
      return {
        id: String(record.get("id")),
        label: String(record.get("label")),
        score: Number(record.get("score") ?? 0),
        type,
        x: pos.x,
        y: pos.y,
      };
    });

    const ids = nodes.map((node) => node.id);
    const edgeResult = await session.run(
      `
      MATCH (a)-[r]->(b)
      WHERE elementId(a) IN $ids AND elementId(b) IN $ids
      RETURN elementId(a) AS fromId, elementId(b) AS toId
      LIMIT $edgeLimit
      `,
      { ids, edgeLimit: neo4j.int(limit * 2) }
    );

    const edges: Neo4jEdge[] = edgeResult.records.map((record: any) => ({
      from: String(record.get("fromId")),
      to: String(record.get("toId")),
    }));

    return { nodes, edges, source: "neo4j" };
  } catch {
    return null;
  } finally {
    await session?.close?.().catch(() => null);
    await driver?.close?.().catch(() => null);
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = Math.max(5, Math.min(80, Number(searchParams.get("limit") ?? "20")));

  const neo4jGraph = await readNeo4jGraph(limit);
  if (neo4jGraph && neo4jGraph.nodes.length > 0) {
    return NextResponse.json({
      nodes: neo4jGraph.nodes,
      edges: neo4jGraph.edges,
      summary: {
        source: "neo4j",
        totalNodes: neo4jGraph.nodes.length,
        totalEdges: neo4jGraph.edges.length,
        visibleNodes: neo4jGraph.nodes.length,
        visibleEdges: neo4jGraph.edges.length,
      },
    });
  }

  const { agents: statAgents, feed } = await readStats();
  const registryAgents = await readRegistryAgents();
  const agents = statAgents.length > 0 ? statAgents : registryAgents;
  const nodes: Array<{ id: string; label: string; type: "agent" | "role" | "event"; x: number; y: number; score?: number }> = [];
  const edges: Array<{ from: string; to: string }> = [];

  const uniqueRoles = [...new Set(agents.map((agent) => agent.role))];

  uniqueRoles.forEach((role, idx) => {
    const pos = polarPosition(idx, uniqueRoles.length, 20);
    nodes.push({ id: `role:${role}`, label: role, type: "role", x: pos.x, y: pos.y });
  });

  agents.forEach((agent, idx) => {
    const pos = polarPosition(idx, Math.max(agents.length, 1), 38);
    nodes.push({
      id: `agent:${agent.name}`,
      label: agent.name,
      type: "agent",
      x: pos.x,
      y: pos.y,
      score: agent.fitness ?? 0,
    });
    edges.push({ from: `agent:${agent.name}`, to: `role:${agent.role}` });
  });

  const recentFeed = feed.slice(-20);
  recentFeed.forEach((item, idx) => {
    const summary = item.summary ?? "Telemetry event";
    const eventId = `event:${idx}`;
    const pos = polarPosition(idx, Math.max(recentFeed.length, 1), 12);
    nodes.push({
      id: eventId,
      label: summary.slice(0, 32),
      type: "event",
      x: pos.x,
      y: pos.y,
    });
    const agent = agents.find((a) => summary.includes(a.name));
    if (agent) {
      edges.push({ from: eventId, to: `agent:${agent.name}` });
    }
  });

  const visibleNodes = nodes.slice(0, limit);
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = edges.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to));

  return NextResponse.json({
    nodes: visibleNodes,
    edges: visibleEdges,
    summary: {
      source: "fallback",
      totalNodes: nodes.length,
      totalEdges: edges.length,
      visibleNodes: visibleNodes.length,
      visibleEdges: visibleEdges.length,
    },
  });
}
