import json
import os
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7693')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')

OUT_HTML = Path('/Users/yamai/Desktop/social-focus-graph.html')
OUT_JSON = Path('/Users/yamai/Desktop/social-focus-graph.json')

LABELS = [
    'Character','Influence','Faction','Observation','Hypothesis','Experiment','Knowledge','Strategy',
    'Event','Goal','Ideology','Belief','Innovation','Memory','Story','HistoricalEvent','CulturalIdentity'
]

REL_TYPES = [
    'RELATIONSHIP','INFLUENCES','MEMBER_OF','OBSERVED','SUGGESTS','SUPPORTS','TESTED_BY','CREATES',
    'VALIDATED_AS','CONTRIBUTES_TO','SHAPES','HOLDS_BELIEF','GENERATED','ADOPTED','SPREADS_TO',
    'HAS_MEMORY','REFERS_TO','REFERS_TO_HISTORY','REFERENCED_BY','PARTICIPATED_IN','PURSUING','HAS_GOAL','FOLLOWS'
]

ANCHORS = [
    'alice',
    'marcus',
    'event_1001',
    'goal_secure_outpost',
    'belief_1',
    'faction_1',
    'action_1',
    'strat_1',
    'observation_1',
    'hypothesis_1',
    'exp_1',
    'knowledge_1',
    'hist_1',
    'story_1',
    'culture_1',
    'innovation_1',
    'influence_1',
    'mem_social_1',
]


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as s:
            nodes = s.run(
                """
                MATCH (seed)
                WHERE seed.id IN $anchors
                MATCH (seed)-[*0..3]-(n)
                WHERE any(lbl IN labels(n) WHERE lbl IN $labels)
                RETURN elementId(n) AS id, labels(n) AS labels, coalesce(n.id,n.name,elementId(n)) AS label
                LIMIT 400
                """,
                labels=LABELS,
                anchors=ANCHORS,
            ).data()
            node_ids = [n['id'] for n in nodes]
            edges = s.run(
                """
                MATCH (a)-[r]->(b)
                WHERE elementId(a) IN $ids AND elementId(b) IN $ids AND type(r) IN $types
                RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS type
                LIMIT 4000
                """,
                ids=node_ids,
                types=REL_TYPES,
            ).data()
    finally:
        driver.close()

    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'nodes': nodes,
        'edges': edges,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding='utf-8')

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Social Focus Graph</title>
<style>
body{{margin:0;background:#111827;color:#e5e7eb;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}#c{{width:100vw;height:100vh;display:block}}.hud{{position:fixed;top:10px;left:10px;background:#0b1225cc;padding:8px 10px;border:1px solid #334155;border-radius:8px;font-size:12px}}
</style></head><body>
<canvas id='c'></canvas><div class='hud' id='hud'></div>
<script>
const DATA={json.dumps(payload)};
const c=document.getElementById('c');const ctx=c.getContext('2d');
function resize(){{c.width=window.innerWidth;c.height=window.innerHeight;}}window.addEventListener('resize',resize);resize();
const nodes=DATA.nodes.map((n,i)=>({{...n,x:c.width/2+Math.cos(i*0.33)*(120+((i%14)*18)),y:c.height/2+Math.sin(i*0.33)*(120+((i%14)*18))}}));
const byId=Object.fromEntries(nodes.map(n=>[n.id,n]));const edges=DATA.edges;
function color(lbl){{const l=(lbl&&lbl[0])||'';return {{Character:'#22c55e',Memory:'#f59e0b',Belief:'#38bdf8',Strategy:'#e879f9',Event:'#f43f5e',Story:'#f97316',Knowledge:'#a3e635',Innovation:'#14b8a6',Influence:'#60a5fa'}}[l]||'#cbd5e1';}}
function draw(){{ctx.clearRect(0,0,c.width,c.height);ctx.globalAlpha=.22;ctx.strokeStyle='#94a3b8';edges.forEach(e=>{{const a=byId[e.source],b=byId[e.target];if(!a||!b)return;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}});
ctx.globalAlpha=1;nodes.forEach(n=>{{ctx.fillStyle=color(n.labels);ctx.beginPath();ctx.arc(n.x,n.y,4.5,0,Math.PI*2);ctx.fill();ctx.fillStyle='#e5e7eb';ctx.font='10px ui-monospace';ctx.fillText(String(n.label),n.x+6,n.y+3);}});
}}
draw();
document.getElementById('hud').textContent=`Nodes: ${{nodes.length}} | Edges: ${{edges.length}}`;
</script></body></html>"""
    OUT_HTML.write_text(html, encoding='utf-8')
    print(json.dumps({'ok':True,'html':str(OUT_HTML),'json':str(OUT_JSON),'nodes':len(nodes),'edges':len(edges)}, indent=2))

if __name__ == '__main__':
    main()
