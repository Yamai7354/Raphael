import asyncio
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List
from src.raphael.core.schemas import SystemEvent, EventType, LayerContext
from src.raphael.core.event_bus import SystemEventBus

app = FastAPI(title="Raphael OS API")
bus = None  # To be injected


class CommandRequest(BaseModel):
    command: str
    priority: int = 5


@app.on_event("startup")
async def startup_event():
    # In a real scenario, we'd connect to a running bus instance
    # For now, this is a placeholder for the API layer
    pass


@app.post("/command")
async def send_command(request: CommandRequest):
    """Submits a user command to the Perception Layer (L2)."""
    if not bus:
        return {"error": "System Bus not connected"}

    event = SystemEvent(
        event_type=EventType.OBSERVATION,
        source_layer=LayerContext(layer_number=1, module_name="API_Interface"),
        priority=request.priority,
        payload={"text": f"user_command: {request.command}"},
    )
    await bus.publish(event)
    return {"status": "Success", "event_id": str(event.event_id)}


@app.get("/health")
async def health_check():
    return {"status": "Raphael OS is alive"}


def run_api(event_bus: SystemEventBus, port: int = 8001):
    global bus
    bus = event_bus
    uvicorn.run(app, host="0.0.0.0", port=port)
