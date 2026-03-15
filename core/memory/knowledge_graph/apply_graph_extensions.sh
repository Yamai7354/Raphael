#!/bin/bash

NEO4J_URL="${NEO4J_HTTP_URI:-http://localhost:7475}/db/neo4j/tx/commit"
NEO4J_AUTH="-u neo4j:${NEO4J_PASSWORD}"

execute_cypher() {
    local cypher="$1"
    echo "Running Cypher: ${cypher:0:100}..."
    curl -s -X POST $NEO4J_URL $NEO4J_AUTH \
        -H "Content-Type: application/json" \
        -d "{\"statements\": [{\"statement\": \"$cypher\"}]}" | grep -i error
}

echo "Step 1: Applying Schema Constraints..."
# Constraints from evolution_schema.cypher
execute_cypher "CREATE CONSTRAINT experiment_id IF NOT EXISTS FOR (e:Experiment) REQUIRE e.id IS UNIQUE;"
execute_cypher "CREATE CONSTRAINT benchmark_id IF NOT EXISTS FOR (b:Benchmark) REQUIRE b.id IS UNIQUE;"
execute_cypher "CREATE CONSTRAINT routing_policy_id IF NOT EXISTS FOR (r:RoutingPolicy) REQUIRE r.id IS UNIQUE;"
execute_cypher "CREATE CONSTRAINT hypothesis_id IF NOT EXISTS FOR (h:Hypothesis) REQUIRE h.id IS UNIQUE;"

echo "Step 2: Implementing Swarm Hierarchy & Delegation..."
execute_cypher "MATCH (director:Agent {name: 'project_sorter_director_agent'}) MATCH (worker:Agent) WHERE worker.name STARTS WITH 'project_sorter_' AND worker.name <> 'project_sorter_director_agent' MERGE (director)-[:MANAGES]->(worker) MERGE (director)-[:DELEGATES_TO]->(worker);"
execute_cypher "MATCH (director:Agent {name: 'portfolio_agent'}) MATCH (worker:Agent) WHERE worker.name STARTS WITH 'portfolio_' AND worker.name <> 'portfolio_agent' MERGE (director)-[:MANAGES]->(worker);"
execute_cypher "MATCH (router:Agent {name: 'router_agent'}) MATCH (other:Agent) WHERE other <> router MERGE (router)-[:DELEGATES_TO]->(other);"

echo "Step 3: Implementing Network Topology..."
execute_cypher "MATCH (mac:Machine {id: 'macbook'}) MATCH (pc:Machine {id: 'desktop'}) MERGE (mac)-[:CONNECTED_TO {type: 'Tailscale', latency_ms: 15}]->(pc) MERGE (pc)-[:CONNECTED_TO {type: 'Tailscale', latency_ms: 15}]->(mac);"

echo "Step 4: Linking Skills to Tools..."
execute_cypher "MATCH (s:Skill {name: 'code_generation'}) MATCH (t:Tool) WHERE t.name CONTAINS 'terminal' OR t.name CONTAINS 'git' OR t.name CONTAINS 'file' MERGE (s)-[:REQUIRES_TOOL]->(t);"
execute_cypher "MATCH (s:Skill {name: 'search_documents'}) MATCH (t:Tool) WHERE t.name CONTAINS 'search' OR t.name CONTAINS 'grep' OR t.name CONTAINS 'read' MERGE (s)-[:REQUIRES_TOOL]->(t);"

echo "Step 5: Implementing Cognitive Pathways..."
execute_cypher "MATCH (a:Agent {name: 'portfolio_agent'}) MATCH (m:Model) WHERE m.name CONTAINS 'deepseek' OR m.name CONTAINS 'llama-3-70b' MERGE (a)-[:PREFERS_MODEL]->(m);"

echo "Step 6: Adding Mock Learning & Evolution Data..."
execute_cypher "MERGE (t:Task {id: 't-101', type: 'refactoring', description: 'Optimize imports'}) MERGE (o:Observation {id: 'obs-1', result: 'Reduced latency by 200ms', timestamp: '$CURRENT_TIME'}) MERGE (t)-[:GENERATED]->(o) WITH o MATCH (p:PerformanceProfile) WHERE p.latency_ms > 0 MERGE (o)-[:UPDATES]->(p);"
execute_cypher "MERGE (e:Experiment {id: 'exp-02', name: 'Llama 3.1 vs 3.2 for Planning'}) WITH e MATCH (m:Model) WHERE m.name CONTAINS 'llama' MERGE (e)-[:TESTED_MODEL]->(m);"
execute_cypher "MERGE (f:Failure {id: 'fail-99', reason: 'Context window exceeded', severity: 'High'}) MERGE (rp:RoutingPolicy {id: 'p-01', strategy: 'ContextAware'}) MERGE (i:Improvement {id: 'imp-01', change: 'Add token chunking layer'}) MERGE (f)-[:IMPROVES]->(rp) MERGE (i)-[:RESOLVES]->(f);"

echo "Graph extensions applied successfully!"
