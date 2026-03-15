"use client";

import { useCallback, useState } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

// Initial dummy graph data pulled from Neo4j mappings
const initialNodes = [
  { id: "1", position: { x: 0, y: 0 }, data: { label: "Task: Data Mining" } },
  {
    id: "2",
    position: { x: -100, y: 100 },
    data: { label: "Habitat: Research" },
  },
  { id: "3", position: { x: 100, y: 100 }, data: { label: "Agent: Planner" } },
];

const initialEdges = [
  { id: "e1-2", source: "1", target: "2", label: "SOLVED_BY" },
  { id: "e2-3", source: "2", target: "3", label: "CONTAINS_AGENT" },
];

export default function GraphCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: any) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div style={{ width: "100vw", height: "100vh" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
      >
        <Controls />
        <MiniMap />
        <Background variant="dots" gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}
