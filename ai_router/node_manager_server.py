from typing import Optional

from fastapi import FastAPI

from ai_router.node_manager import NodeManager, NodeRegistration, NodeRole

app = FastAPI(title="Node Manager Service", version="1.0.0")
manager = NodeManager()


@app.on_event("startup")
async def startup_event():
    await manager.start()


@app.on_event("shutdown")
async def shutdown_event():
    await manager.stop()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "node_manager"}


@app.post("/swarm/register")
async def register_swarm_node(registration: NodeRegistration):
    return manager.register_node(registration)


@app.post("/swarm/heartbeat/{node_id}")
async def heartbeat_swarm_node(node_id: str, payload: dict):
    return manager.heartbeat(node_id, payload.get("gpu_load", 0.0), payload.get("queue_size", 0))


@app.get("/swarm/nodes")
async def get_swarm_nodes(role: Optional[NodeRole] = None):
    nodes = manager.get_available_nodes(role)
    return {"status": "success", "nodes": [n.model_dump() for n in nodes]}
