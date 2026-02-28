import json
import os
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

REPORT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'social_graph_stitch_report.json'

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7693')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')

QUERIES = [
    # Ensure key nodes from diagram exist.
    "MERGE (:Character {id:'marcus', name:'Marcus', role:'strategist'})",
    "MERGE (:Influence {id:'influence_1', topic:'resource_scarcity'})",
    "MERGE (:Innovation {id:'innovation_1', title:'Adaptive treaty protocol'})",
    "MERGE (:Memory {id:'mem_social_1', emotional_weight:0.7, interpretation:'Alliance strain observed'})",

    # Relationship-style ties from diagram.
    "MATCH (a:Character {id:'alice'}), (m:Character {id:'marcus'}) MERGE (a)-[:RELATIONSHIP {trust:0.4,fear:0.1,respect:0.6,hostility:0.3,last_updated:datetime()}]->(m)",
    "MATCH (c:Character {id:'alice'}), (i:Influence {id:'influence_1'}) MERGE (c)-[:INFLUENCES]->(i)",
    "MATCH (i:Influence {id:'influence_1'}), (h:Hypothesis {id:'hypothesis_1'}) MERGE (i)-[:INFLUENCES]->(h)",
    "MATCH (f:Faction {id:'faction_1'}), (i:Influence {id:'influence_1'}) MERGE (f)-[:MEMBER_OF]->(i)",
    "MATCH (o:Observation {id:'observation_1'}), (h:Hypothesis {id:'hypothesis_1'}) MERGE (o)-[:SUGGESTS]->(h)",
    "MATCH (h:Hypothesis {id:'hypothesis_1'}), (e:Experiment {id:'exp_1'}) MERGE (h)-[:TESTED_BY]->(e)",
    "MATCH (e:Experiment {id:'exp_1'}), (k:Knowledge {id:'knowledge_1'}) MERGE (e)-[:CREATES]->(k)",
    "MATCH (h:Hypothesis {id:'hypothesis_1'}), (k:Knowledge {id:'knowledge_1'}) MERGE (h)-[:VALIDATED_AS]->(k)",
    "MATCH (b:Belief {id:'belief_1'}), (ci:CulturalIdentity {id:'culture_1'}) MERGE (b)-[:CONTRIBUTES_TO]->(ci)",
    "MATCH (s:Strategy {id:'strat_1'}), (ci:CulturalIdentity {id:'culture_1'}) MERGE (s)-[:SHAPES]->(ci)",
    "MATCH (i:Innovation {id:'innovation_1'}), (b:Belief {id:'belief_1'}) MERGE (i)-[:GENERATED]->(b)",
    "MATCH (i:Innovation {id:'innovation_1'}), (c:Character {id:'alice'}) MERGE (i)-[:ADOPTED]->(c)",
    "MATCH (i:Innovation {id:'innovation_1'}), (m:Character {id:'marcus'}) MERGE (i)-[:SPREADS_TO]->(m)",
    "MATCH (c:Character {id:'alice'}), (m:Memory {id:'mem_social_1'}) MERGE (c)-[:HAS_MEMORY]->(m)",
    "MATCH (m:Memory {id:'mem_social_1'}), (e:Event {id:'event_1001'}) MERGE (m)-[:REFERS_TO]->(e)",
    "MATCH (st:Story {id:'story_1'}), (h:HistoricalEvent {id:'hist_1'}) MERGE (st)-[:REFERS_TO_HISTORY]->(h)",
    "MATCH (st:Story {id:'story_1'}), (m:Memory {id:'mem_social_1'}) MERGE (st)-[:REFERENCED_BY]->(m)",
    "MATCH (s:Strategy {id:'strat_1'}), (e:Event {id:'event_1001'}) MERGE (s)-[:TESTED_BY]->(e)",
]


def main() -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    run = 0
    errors = []

    try:
        with driver.session() as session:
            for query in QUERIES:
                try:
                    session.run(query).consume()
                    run += 1
                except Exception as exc:
                    errors.append({'query': query, 'error': str(exc)[:500]})

            node_counts = session.run(
                "MATCH (n) WHERE any(lbl IN labels(n) WHERE lbl IN ['Character','Influence','Faction','Observation','Hypothesis','Experiment','Knowledge','Strategy','Event','Goal','Ideology','Belief','Innovation','Memory','Story','HistoricalEvent','CulturalIdentity']) RETURN labels(n) AS labels, count(*) AS count ORDER BY count DESC"
            ).data()
            rel_counts = session.run(
                "MATCH ()-[r]->() WHERE type(r) IN ['RELATIONSHIP','INFLUENCES','MEMBER_OF','OBSERVED','SUGGESTS','SUPPORTS','TESTED_BY','CREATES','VALIDATED_AS','CONTRIBUTES_TO','SHAPES','HOLDS_BELIEF','GENERATED','ADOPTED','SPREADS_TO','HAS_MEMORY','REFERS_TO','REFERS_TO_HISTORY','REFERENCED_BY','PARTICIPATED_IN','PURSUING','HAS_GOAL','FOLLOWS'] RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"
            ).data()
    finally:
        driver.close()

    report = {
        'ok': len(errors) == 0,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'queries_attempted': len(QUERIES),
        'queries_successful': run,
        'errors': errors,
        'node_counts_focus': node_counts,
        'relationship_counts_focus': rel_counts,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
