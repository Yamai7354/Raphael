import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi.middleware.cors import CORSMiddleware
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from .node_state import NodeState
from .policy import policy_registry
from pydantic import BaseModel
from .roles import role_registry
from .state_cache import node_cache
from event_bus.redis_bus import RedisEventBus
from event_bus.event_bus import Event
from . import bus  # Import the singleton module
from .perception import perception_service  # Import perception service
from core.memory.episodic_memory.episodic_memory import episodic_memory  # Import episodic memory
from .knowledge import knowledge_graph  # Import knowledge graph
from .working_memory import working_memory  # Import working memory
from .resource import resource_manager  # Import resource manager
from .evaluation import evaluation_service
from .transparency_stream import format_sse, transparency_stream
from .node_manager import NodeManager, NodeRegistration, NodeRole
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("ai_router.main")

# Global config storage
config: Dict[str, Any] = {}

# Global Node Manager
swarm_node_manager = NodeManager(heartbeat_timeout_seconds=30)


def _publish_transparency_event(
    event_type: str,
    message: str,
    correlation_id: Optional[str] = None,
    task_id: Optional[str] = None,
    node_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Fire-and-forget publisher for transparency SSE events."""
    asyncio.create_task(
        transparency_stream.publish(
            {
                "type": event_type,
                "correlation_id": correlation_id,
                "task_id": task_id,
                "node_id": node_id,
                "message": message,
                "details": details or {},
            }
        )
    )


def load_config():
    """Load configuration from config.json."""
    global config
    try:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)

        # Each node now uses its own URL from config.json.
        # Do NOT override node URLs — desktop (LM Studio) and mac (Ollama)
        # run separate registries and must not be collapsed.
        logger.info("Config loaded successfully.")
    except Exception as e:
        logger.error("Error loading config: %s", e)
        config = {"nodes": [], "roles": [], "policy": {}}


def load_policy():
    """Load runtime policy from config. Fails fast on invalid policy."""
    policy_config = config.get("policy", {})
    if policy_config:
        policy_registry.load_from_config(policy_config)
    else:
        policy_registry.load_defaults()


def load_roles():
    """Load roles from config into the role registry. Fails fast on invalid roles."""
    roles_config = config.get("roles", [])
    if not roles_config:
        logger.warning("No roles configured. Role-based routing will not work.")
        return
    role_registry.load_from_config(roles_config)

    # Validate roles against policy
    validator = policy_registry.validator
    for role_id in role_registry.list_role_ids():
        role = role_registry.get_role(role_id)
        is_valid, error = validator.validate_role_context(role.max_context_tokens)
        if not is_valid:
            raise ValueError(f"Role '{role_id}' violates policy: {error}")
        is_valid, error = validator.validate_quantization(role.quantization_policy)
        if not is_valid:
            raise ValueError(f"Role '{role_id}' violates policy: {error}")


def load_capabilities():
    """Load node capabilities from config. Required for role placement."""
    from .capabilities import capability_registry

    nodes_config = config.get("nodes", [])
    if nodes_config:
        capability_registry.load_from_config(nodes_config)


def load_model_mappings():
    """Load role-to-model mappings from config."""
    from .model_mapping import model_mapping_registry

    mappings_config = config.get("model_mappings", [])
    if mappings_config:
        model_mapping_registry.load_from_config(mappings_config)
    else:
        logger.warning("No model_mappings configured. Model selection will fail.")


def register_nodes():
    """Register all nodes from config into the state cache with initial OFFLINE state."""
    nodes = config.get("nodes", [])
    for node in nodes:
        # Pass the entire node config dictionary as attributes
        # This ensures static nodes have 'url', 'role', etc. in the cache
        node_cache.register_node(node["id"], NodeState.OFFLINE, attributes=node)
    logger.info("Registered %d nodes.", len(nodes))


async def monitor_nodes():
    """Background task to periodically check node health and readiness."""
    logger.info("Starting node health monitor loop...")
    while True:
        try:
            nodes = config.get("nodes", [])
            if nodes:
                async with httpx.AsyncClient() as client:
                    tasks = [check_node_full(node, client) for node in nodes]
                    await asyncio.gather(*tasks)
            await asyncio.sleep(30)  # Check every 30 seconds
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in health monitor loop: %s", e)
            await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialization
    load_config()

    # Initialize Event Bus
    global event_bus
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    # Parse redis_url (simple parsing for now, assuming standard format)
    # redis://host:port/db
    try:
        if redis_url.startswith("redis://"):
            parts = redis_url.replace("redis://", "").split(":")
            host = parts[0]
            port_db = parts[1].split("/")
            port = int(port_db[0])
            db = int(port_db[1]) if len(port_db) > 1 else 0
        else:
            host = "localhost"
            port = 6379
            db = 0

        bus.event_bus = RedisEventBus(host=host, port=port, db=db, source_name="raphael-core")
        # Keep legacy alias for existing references in this module.
        event_bus = bus.event_bus
        await bus.event_bus.connect()

        await bus.event_bus.publish(
            Event(
                topic="system.startup",
                payload={"status": "online", "service": "raphael-core"},
            )
        )
        logger.info("Event Bus initialized and startup event published.")

        # Start Perception Service
        await perception_service.start()

        # Start Episodic Memory
        await episodic_memory.start()

        # Start Knowledge Graph
        await knowledge_graph.start()

        # Start Working Memory
        await working_memory.start()

        # Start Resource Manager
        await resource_manager.start()
        await evaluation_service.start()
        # Start Reflection Engine
        from .reflection import reflection_engine

        await reflection_engine.start()
        from .experiment import experiment_manager

        await experiment_manager.start()
        # Start Audio Interaction
        from .interaction import interaction_manager

        await interaction_manager.start()
    except Exception as e:
        logger.error(f"Failed to initialize Event Bus: {e}")

    load_policy()
    load_roles()
    load_capabilities()
    load_model_mappings()
    register_nodes()

    # 2. Start background tasks
    from .adaptive_policy_engine import adaptive_engine
    from .auto_scaler import auto_scaler
    from .federation_manager import federation_manager
    from .workflow_supervisor import workflow_supervisor

    await swarm_node_manager.start()

    tasks = [
        asyncio.create_task(auto_scaler.run_loop()),
        asyncio.create_task(federation_manager.start_monitoring()),
        asyncio.create_task(adaptive_engine.run_loop()),
        asyncio.create_task(workflow_supervisor.run_loop()),
        asyncio.create_task(monitor_nodes()),
    ]

    yield

    # 3. Cleanup
    for task in tasks:
        task.cancel()
    # Wait for tasks to cancel
    await asyncio.gather(*tasks, return_exceptions=True)

    await perception_service.stop()
    await episodic_memory.stop()
    await knowledge_graph.stop()
    await working_memory.stop()
    await evaluation_service.stop()
    from .reflection import reflection_engine

    await reflection_engine.stop()
    from .experiment import experiment_manager

    await experiment_manager.stop()
    from .interaction import interaction_manager

    await interaction_manager.stop()
    await swarm_node_manager.stop()

    if bus.event_bus:
        await bus.event_bus.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint to verify server is running."""
    return {
        "status": "online",
        "message": "AI Router is running",
        "docs": "/docs",
        "dashboard": "/admin/dashboard",  # If this exists, otherwise /docs
    }


# --- SWARM NODE MANAGER ROUTES ---
@app.post("/swarm/register")
async def register_swarm_node(registration: NodeRegistration):
    """Register a new node into the swarm cluster."""
    return swarm_node_manager.register_node(registration)


@app.post("/swarm/deregister/{node_id}")
async def deregister_swarm_node(node_id: str):
    """Remove a node from the swarm cluster."""
    return swarm_node_manager.deregister_node(node_id)


@app.post("/swarm/heartbeat/{node_id}")
async def heartbeat_swarm_node(node_id: str, payload: dict):
    """Ping the manager to report online status and load metrics."""
    # payload: {"gpu_load": 0.5, "queue_size": 2}
    return swarm_node_manager.heartbeat(
        node_id, payload.get("gpu_load", 0.0), payload.get("queue_size", 0)
    )


@app.get("/swarm/nodes")
async def get_swarm_nodes(role: Optional[NodeRole] = None):
    """Get all available nodes, optionally filtered by role."""
    nodes = swarm_node_manager.get_available_nodes(role)
    return {"status": "success", "nodes": [n.model_dump() for n in nodes]}


# ---------------------------------


async def check_node_health(node: Dict[str, Any], client: httpx.AsyncClient) -> None:
    """
    Check the CONTROL-PLANE health of a node (fast).
    Handles cooldown entry on failure and recovery confirmation.
    """
    node_id = node["id"]
    node_info = node_cache.get_node(node_id)
    previous_state = node_info.state.value if node_info else None
    start_time = time.time()
    url = f"{node['url'].rstrip('/')}/models"

    try:
        response = await client.get(url, timeout=node.get("timeout", 5.0))
        latency_ms = (time.time() - start_time) * 1000

        if response.status_code == 200:
            node_cache.update_latency(node_id, round(latency_ms, 2))

            # If in cooldown, require confirmation before transitioning
            if node_info and node_info.is_in_cooldown():
                if node_info.confirm_recovery():
                    # Cooldown cleared, transition to ONLINE
                    node_cache.update_state(node_id, NodeState.ONLINE, "recovery_confirmed")
                    node_cache.reset_error_count(node_id)
                # else: stay in current state, awaiting more confirmations
            else:
                # Not in cooldown, normal transition
                # Prevent degrading READY state to ONLINE
                if node_info.state != NodeState.READY:
                    node_cache.update_state(node_id, NodeState.ONLINE, "health_check_success")
                node_cache.reset_error_count(node_id)
        else:
            # Non-200 response -> DEGRADED + enter cooldown
            node_cache.update_state(
                node_id,
                NodeState.DEGRADED,
                f"health_check_error_status_{response.status_code}",
            )
            node_cache.increment_error_count(node_id)
            if node_info:
                node_info.enter_cooldown(f"status_{response.status_code}")

    except httpx.TimeoutException:
        node_cache.update_state(node_id, NodeState.OFFLINE, "health_check_timeout")
        node_cache.increment_error_count(node_id)
        if node_info:
            node_info.enter_cooldown("timeout")
    except Exception as e:
        node_cache.update_state(
            node_id, NodeState.OFFLINE, f"health_check_exception_{type(e).__name__}"
        )
        node_cache.increment_error_count(node_id)
        if node_info:
            node_info.enter_cooldown(f"exception_{type(e).__name__}")
    finally:
        current_info = node_cache.get_node(node_id)
        current_state = current_info.state.value if current_info else None
        if previous_state and current_state and previous_state != current_state:
            _publish_transparency_event(
                event_type="node_state",
                message=f"Node {node_id} transitioned {previous_state} -> {current_state}",
                node_id=node_id,
                details={
                    "previous_state": previous_state,
                    "current_state": current_state,
                    "reason": current_info.last_transition_reason if current_info else None,
                    "latency_ms": current_info.latency_ms if current_info else None,
                },
            )


async def check_node_readiness(node: Dict[str, Any], client: httpx.AsyncClient) -> None:
    """
    Check if a node is READY for inference (slower, explicit).
    Only call this for nodes that are ONLINE and NOT in cooldown.
    """
    node_id = node["id"]
    node_info = node_cache.get_node(node_id)
    previous_state = node_info.state.value if node_info else None

    # Only check readiness for ONLINE nodes that are not in cooldown
    if node_info is None:
        return
    if node_info.state != NodeState.ONLINE:
        return
    if node_info.is_in_cooldown():
        logger.debug("node_id=%s skipping readiness check (in cooldown)", node_id)
        return

    url = f"{node['url'].rstrip('/')}/models"

    try:
        response = await client.get(url, timeout=node.get("timeout", 5.0))

        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])

            if models and len(models) > 0:
                # Update capability registry with discovered models
                from .capabilities import capability_registry

                model_ids = [m.get("id") for m in models if isinstance(m, dict) and "id" in m]
                capability_registry.update_node_models(node_id, model_ids)

                # At least one model is loaded -> READY
                node_cache.update_state(node_id, NodeState.READY, "readiness_check_model_loaded")
            else:
                # No models loaded -> WARMING
                node_cache.update_state(node_id, NodeState.WARMING, "readiness_check_no_models")
        else:
            logger.warning(
                "node_id=%s readiness_check returned status=%d",
                node_id,
                response.status_code,
            )

    except Exception as e:
        logger.warning("node_id=%s readiness_check_exception=%s", node_id, type(e).__name__)
    finally:
        current_info = node_cache.get_node(node_id)
        current_state = current_info.state.value if current_info else None
        if previous_state and current_state and previous_state != current_state:
            _publish_transparency_event(
                event_type="node_state",
                message=f"Node {node_id} transitioned {previous_state} -> {current_state}",
                node_id=node_id,
                details={
                    "previous_state": previous_state,
                    "current_state": current_state,
                    "reason": current_info.last_transition_reason if current_info else None,
                    "latency_ms": current_info.latency_ms if current_info else None,
                },
            )


async def check_node_full(node: Dict[str, Any], client: httpx.AsyncClient) -> None:
    """
    Perform both health and readiness checks on a node.
    """
    await check_node_health(node, client)
    await check_node_readiness(node, client)


@app.get("/health")
async def health_check():
    """
    Ping all nodes in config to check their status.
    Returns full cluster view with summary for monitoring.
    """
    nodes = config.get("nodes", [])
    if not nodes:
        return {"error": "No nodes configured", "nodes": {}}

    async with httpx.AsyncClient() as client:
        tasks = [check_node_full(node, client) for node in nodes]
        await asyncio.gather(*tasks)

    # Build cluster state
    cluster_state = node_cache.to_dict()

    # Build summary
    state_counts: Dict[str, int] = {}
    ready_count = 0
    cooldown_count = 0

    for node_id, info in cluster_state.items():
        state = info["state"]
        state_counts[state] = state_counts.get(state, 0) + 1
        if state == "READY":
            ready_count += 1
        if info.get("in_cooldown"):
            cooldown_count += 1

    return {
        "status": "completed",
        "summary": {
            "total_nodes": len(cluster_state),
            "ready_count": ready_count,
            "cooldown_count": cooldown_count,
            "state_counts": state_counts,
        },
        "cluster_state": cluster_state,
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Dict[str, Any]):
    """
    Proxy chat completions to a READY node.
    Uses router guardrails to select the best node.

    Fails with HTTP 503 if no READY nodes are available.
    """
    from .capabilities import capability_registry
    from .model_mapping import model_mapping_registry
    from .placement import placement_registry
    from .roles import role_registry
    from .router import routing_guardrail

    # Determine role from request
    role_id = request.get("role")

    # Allow model name to act as role ID if role not explicitly set
    if not role_id:
        model_id = request.get("model")
        if model_id and role_registry.get_role(model_id):
            role_id = model_id
            logger.info(f"Inferring role='{role_id}' from model parameter")

    selected_node = None

    # If role is provided, use smart capability-based routing
    if role_id:
        # 1. Resolve Model
        mapping = model_mapping_registry.get_mapping(role_id)
        if mapping:
            model_spec = mapping.get_preferred_model()
            if model_spec:
                request["model"] = model_spec.model_id
                logger.info(f"Resolved role={role_id} to model='{model_spec.model_id}'")

        # 2. Get Role Definition
        role_def = role_registry.get_role(role_id)
        if role_def:
            # 3. Filter Compatible Nodes
            compatible_nodes = []
            for node_id in node_cache.get_ready_nodes():
                # Load check first
                if not await resource_manager.can_accept_task(node_id):
                    logger.debug(f"node_id={node_id} omitted due to high load")
                    continue

                caps = capability_registry.get_capabilities(node_id)
                if caps:
                    can_host, reason = caps.can_host_role(role_def)
                    if can_host:
                        compatible_nodes.append(node_id)
                    else:
                        logger.debug(f"node_id={node_id} incompatible reason={reason}")

            if compatible_nodes:
                # 4. Select Best Node (Latency)
                best_latency = float("inf")
                selected_node_id = None

                # Prefer existing placement
                existing = placement_registry.get_ready_placement_for_role(role_id)
                if existing and existing.node_id in compatible_nodes:
                    selected_node_id = existing.node_id
                    existing.touch()
                else:
                    for node_id in compatible_nodes:
                        node_info = node_cache.get_node(node_id)
                        if node_info and node_info.latency_ms is not None:
                            if node_info.latency_ms < best_latency:
                                best_latency = node_info.latency_ms
                                selected_node_id = node_id
                    if not selected_node_id:
                        selected_node_id = compatible_nodes[0]

                # Get Config for selected node
                for node in config.get("nodes", []):
                    if node["id"] == selected_node_id:
                        selected_node = node
                        break

    # Fallback to standard routing if no role or smart routing failed
    if not selected_node:
        selected_node = await routing_guardrail(role_id, config)

    # Forward request to the selected node
    url = f"{selected_node['url'].rstrip('/')}/chat/completions"
    timeout = selected_node.get("timeout", 60.0)

    logger.info(f"Forwarding to node={selected_node['id']} url={url} payload={request}")

    # Handle Streaming
    if request.get("stream"):

        async def stream_proxy():
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    async with client.stream("POST", url, json=request) as response:
                        if response.status_code != 200:
                            yield f'data: {{"error": "Node returned {response.status_code}"}}\n\n'
                            return

                        async for line in response.aiter_lines():
                            if line:
                                yield f"{line}\n"
                except Exception as e:
                    logger.error(f"Streaming error provided by node {selected_node['id']}: {e}")
                    yield f'data: {{"error": "Streaming failed: {str(e)}"}}\n\n'

        return StreamingResponse(stream_proxy(), media_type="text/event-stream")

    # Handle Normal Request (Non-Streaming)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=request,
                timeout=timeout,
            )
            result = response.json()

            # Inject routing metadata for debugging
            if isinstance(result, dict) and role_id:
                result["_routing"] = {
                    "role": role_id,
                    "node": selected_node.get("id"),
                    "model": request.get("model"),
                }
            return result
        except httpx.TimeoutException:
            # Mark node as degraded on timeout during inference
            node_info = node_cache.get_node(selected_node["id"])
            if node_info:
                node_cache.update_state(
                    selected_node["id"], NodeState.DEGRADED, "inference_timeout"
                )
                node_info.enter_cooldown("inference_timeout")
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "gateway_timeout",
                    "message": f"Node {selected_node['id']} timed out during inference",
                    "node_id": selected_node["id"],
                },
            )
        except Exception as e:
            logger.error(
                "node_id=%s inference_exception=%s",
                selected_node["id"],
                type(e).__name__,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "bad_gateway",
                    "message": f"Error forwarding to node: {type(e).__name__}",
                    "node_id": selected_node["id"],
                },
            )


@app.post("/run")
async def run_role_request(request: Dict[str, Any]):
    """
    Role-based inference endpoint.
    Client specifies role, router resolves model and node.

    Request format:
    {
        "role": "coder",
        "messages": [...],
        "input": "optional raw input"
    }

    Fails with HTTP 503 if role cannot be satisfied.
    """
    from .capabilities import capability_registry
    from .model_mapping import model_mapping_registry
    from .placement import placement_registry
    from .roles import role_registry

    # 1. Validate role
    role_id = request.get("role")
    if not role_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_role",
                "message": "Request must include 'role' field",
            },
        )

    role = role_registry.get_role(role_id)
    if not role:
        raise HTTPException(
            status_code=400,
            detail={"error": "unknown_role", "message": f"Role '{role_id}' not found"},
        )

    # 2. Find compatible nodes (READY state + capability match)
    compatible_nodes = []
    for node_id in node_cache.get_ready_nodes():
        # Load check first
        if not await resource_manager.can_accept_task(node_id):
            logger.debug("node_id=%s omitted due to high load", node_id)
            continue

        caps = capability_registry.get_capabilities(node_id)
        if caps:
            can_host, reason = caps.can_host_role(role)
            if can_host:
                compatible_nodes.append(node_id)
            else:
                logger.debug("node_id=%s incompatible reason=%s", node_id, reason)

    if not compatible_nodes:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no_compatible_nodes",
                "message": f"No READY nodes can satisfy role '{role_id}'",
                "role_id": role_id,
            },
        )

    # 3. Select best node (prefer existing placement, then lowest latency)
    selected_node_id = None

    # Check for existing ready placement
    existing = placement_registry.get_ready_placement_for_role(role_id)
    if existing and existing.node_id in compatible_nodes:
        selected_node_id = existing.node_id
        existing.touch()  # Update last_used
    else:
        # Select by lowest latency
        best_latency = float("inf")
        for node_id in compatible_nodes:
            node_info = node_cache.get_node(node_id)
            if node_info and node_info.latency_ms is not None:
                if node_info.latency_ms < best_latency:
                    best_latency = node_info.latency_ms
                    selected_node_id = node_id
        if not selected_node_id:
            selected_node_id = compatible_nodes[0]

    # 4. Get node config
    node_config = None
    for node in config.get("nodes", []):
        if node["id"] == selected_node_id:
            node_config = node
            break

    if not node_config:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "config_error",
                "message": f"Node {selected_node_id} not in config",
            },
        )

    # 5. Get model mapping
    mapping = model_mapping_registry.get_mapping(role_id)
    if not mapping or not mapping.models:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no_model_mapping",
                "message": f"No models configured for role '{role_id}'",
            },
        )
    model_spec = mapping.get_preferred_model()

    logger.info(
        "role_routing role=%s model=%s node=%s",
        role_id,
        model_spec.model_id,
        selected_node_id,
    )

    # 6. Build messages (handling raw input if provided)
    messages = request.get("messages", [])
    if "input" in request and not messages:
        messages = [{"role": "user", "content": request["input"]}]

    # 7. Enforce context limits
    from .context import enforce_context_limit

    check, messages = enforce_context_limit(
        messages,
        role.max_context_tokens,
        strict=request.get("strict_context", False),  # Optional strict mode
    )

    context_warning = None
    if check.warning:
        logger.warning("context_warning role=%s warning=%s", role_id, check.warning)
        context_warning = check.warning

    # 8. Build inference request
    inference_request = {
        "model": model_spec.model_id,
        "messages": messages,
        "temperature": role.default_temperature,
        "max_tokens": min(role.max_context_tokens // 4, 4096),  # Response limit ~25% of context
    }

    url = f"{node_config['url'].rstrip('/')}/chat/completions"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=inference_request,
                timeout=node_config.get("timeout", 30.0),
            )
            result = response.json()

            # Add routing metadata
            result["_routing"] = {
                "role": role_id,
                "model": model_spec.model_id,
                "node": selected_node_id,
            }
            if context_warning:
                result["_routing"]["context_warning"] = context_warning
            return result

        except httpx.TimeoutException:
            node_info = node_cache.get_node(selected_node_id)
            if node_info:
                node_cache.update_state(selected_node_id, NodeState.DEGRADED, "inference_timeout")
                node_info.enter_cooldown("inference_timeout")
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "gateway_timeout",
                    "message": f"Node {selected_node_id} timed out during inference",
                    "role": role_id,
                    "node_id": selected_node_id,
                },
            )
        except Exception as e:
            logger.error(
                "role_inference_error role=%s node=%s error=%s",
                role_id,
                selected_node_id,
                type(e).__name__,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "bad_gateway",
                    "message": f"Error forwarding to node: {type(e).__name__}",
                    "role": role_id,
                    "node_id": selected_node_id,
                },
            )


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================


@app.get("/admin/roles")
async def list_roles():
    """List all configured roles."""
    from .roles import role_registry

    roles = []
    for role_id in role_registry.list_role_ids():
        role = role_registry.get_role(role_id)
        roles.append(
            {
                "role_id": role.role_id,
                "description": role.description,
                "max_context_tokens": role.max_context_tokens,
                "preferred_model_size_max": role.preferred_model_size_max,
                "quantization_policy": role.quantization_policy.value,
                "default_temperature": role.default_temperature,
                "latency_sensitive": role.latency_sensitive,
            }
        )
    return {"roles": roles, "count": len(roles)}


@app.get("/admin/placements")
async def list_placements():
    """List all current role placements across nodes."""
    from .placement import placement_registry

    return {
        "placements": placement_registry.to_dict(),
    }


@app.get("/admin/nodes")
async def list_nodes_admin():
    """Get detailed node status with capabilities."""
    from .capabilities import capability_registry

    nodes = []
    for node in config.get("nodes", []):
        node_id = node["id"]
        node_info = node_cache.get_node(node_id)
        caps = capability_registry.get_capabilities(node_id)

        node_data = {
            "id": node_id,
            "name": node.get("name"),
            "url": node.get("url"),
            "state": node_info.state.value if node_info else "UNKNOWN",
            "latency_ms": node_info.latency_ms if node_info else None,
        }

        if caps:
            node_data["capabilities"] = {
                "max_context_supported": caps.max_context_supported,
                "supported_model_sizes": caps.supported_model_sizes,
                "supported_quantizations": [q.value for q in caps.supported_quantizations],
                "concurrent_role_limit": caps.concurrent_role_limit,
            }

        if node_info and node_info.is_in_cooldown():
            node_data["cooldown_remaining_sec"] = node_info.cooldown_remaining_sec()

        nodes.append(node_data)

    return {"nodes": nodes, "count": len(nodes)}


@app.get("/admin/model-mappings")
async def list_model_mappings():
    """List all role-to-model mappings."""
    from .model_mapping import model_mapping_registry

    mappings = []
    for role_id in role_registry.list_role_ids():
        mapping = model_mapping_registry.get_mapping(role_id)
        if mapping:
            mappings.append(
                {
                    "role_id": role_id,
                    "preferred_model": mapping.get_preferred_model().model_id
                    if mapping.models
                    else None,
                    "model_count": len(mapping.models),
                    "models": [
                        {
                            "model_id": m.model_id,
                            "size": m.size,
                            "context_length": m.context_length,
                        }
                        for m in mapping.models
                    ],
                }
            )
    return {"model_mappings": mappings}


@app.post("/admin/placements/{node_id}/load")
async def load_role_on_node(node_id: str, request: Dict[str, Any]):
    """
    Load a role's model onto a specific node.
    Request: {"role_id": "coder"}
    """
    from .capabilities import capability_registry
    from .lmstudio_adapter import lmstudio_adapter
    from .model_mapping import model_mapping_registry
    from .placement import placement_registry
    from .roles import role_registry

    role_id = request.get("role_id")
    if not role_id:
        raise HTTPException(status_code=400, detail={"error": "missing_role_id"})

    role = role_registry.get_role(role_id)
    if not role:
        raise HTTPException(status_code=400, detail={"error": "unknown_role", "role_id": role_id})

    # Check node exists and is ready
    node_config = None
    for node in config.get("nodes", []):
        if node["id"] == node_id:
            node_config = node
            break

    if not node_config:
        raise HTTPException(status_code=404, detail={"error": "node_not_found", "node_id": node_id})

    # Check capabilities
    caps = capability_registry.get_capabilities(node_id)
    if caps:
        can_host, reason = caps.can_host_role(role)
        if not can_host:
            raise HTTPException(
                status_code=400, detail={"error": "incompatible_node", "reason": reason}
            )

    # Get model mapping
    mapping = model_mapping_registry.get_mapping(role_id)
    if not mapping or not mapping.models:
        raise HTTPException(
            status_code=400, detail={"error": "no_model_mapping", "role_id": role_id}
        )

    model_spec = mapping.get_preferred_model()

    # Create placement
    try:
        placement = placement_registry.create_placement(role_id, model_spec.model_id, node_id)
    except ValueError as e:
        raise HTTPException(
            status_code=409, detail={"error": "placement_conflict", "message": str(e)}
        )

    # Build and send load params
    node_max_context = caps.max_context_supported if caps else 32768
    params = lmstudio_adapter.build_load_params(role, model_spec, node_max_context)

    success, message = await lmstudio_adapter.load_model(node_config["url"], params)

    if success:
        placement.mark_ready()
        return {
            "status": "loaded",
            "role_id": role_id,
            "model_id": model_spec.model_id,
            "node_id": node_id,
        }
    else:
        placement_registry.remove_placement(node_id, role_id)
        raise HTTPException(status_code=500, detail={"error": "load_failed", "message": message})


@app.delete("/admin/placements/{node_id}/{role_id}")
async def unload_role_from_node(node_id: str, role_id: str):
    """Unload a role's model from a node."""
    from .lmstudio_adapter import lmstudio_adapter
    from .placement import placement_registry

    placement = placement_registry.get_placement(node_id, role_id)
    if not placement:
        raise HTTPException(status_code=404, detail={"error": "placement_not_found"})

    # Get node URL
    node_url = None
    for node in config.get("nodes", []):
        if node["id"] == node_id:
            node_url = node["url"]
            break

    if node_url:
        placement.mark_draining()
        success, message = await lmstudio_adapter.unload_model(node_url, placement.model_id)

    removed = placement_registry.remove_placement(node_id, role_id)

    return {
        "status": "unloaded" if removed else "not_found",
        "role_id": role_id,
        "node_id": node_id,
    }


@app.get("/admin/policy")
async def get_policy():
    """Get current runtime policy."""
    from policy import policy_registry

    policy = policy_registry.policy
    return {
        "global_max_context_tokens": policy.global_max_context_tokens,
        "default_quantization": policy.default_quantization.value,
        "max_concurrent_requests_per_node": policy.max_concurrent_requests_per_node,
        "request_timeout_seconds": policy.request_timeout_seconds,
        "allow_runtime_role_changes": policy.allow_runtime_role_changes,
        "allow_runtime_policy_changes": policy.allow_runtime_policy_changes,
    }


# =============================================================================
# PLANNER ENDPOINTS
# =============================================================================


@app.post("/planner/plan")
async def create_plan(request: Dict[str, Any], v: str = "1"):
    """
    Dedicated Planner Endpoint - Task Decomposition.

    Deterministically decomposes a task into subtasks.
    Same input → same subtasks (reproducible).

    Query params:
        v: API version (default "1")

    Input:
    {
        "task_id": "string",
        "objective": "string",
        "constraints": ["string"],
        "context": "optional string or JSON"
    }

    Output:
    {
        "task_id": "string",
        "subtasks": [...],
        "metadata": {...}
    }
    """
    from .planner import PlannerConfig, PlanRequest, planner_registry, validate_plan
    from pydantic import ValidationError

    # Validate version
    if v not in PlannerConfig.SUPPORTED_VERSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_version",
                "version": v,
                "supported": list(PlannerConfig.SUPPORTED_VERSIONS),
            },
        )

    # Validate input schema
    try:
        plan_request = PlanRequest(**request)
    except ValidationError as e:
        logger.warning("plan_request_invalid errors=%s", e.errors())
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": "Request validation failed",
                "validation_errors": e.errors(),
            },
        )

    # Get planner for version
    planner_func = planner_registry.get_planner(v)

    # Generate plan
    try:
        plan = planner_func(plan_request, v)
    except Exception as e:
        logger.error("plan_generation_failed task_id=%s error=%s", plan_request.task_id, str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "plan_generation_failed",
                "task_id": plan_request.task_id,
                "message": str(e),
            },
        )

    # Validate output schema
    is_valid, error = validate_plan(plan)
    if not is_valid:
        logger.error("plan_validation_failed task_id=%s error=%s", plan_request.task_id, error)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "plan_validation_failed",
                "task_id": plan_request.task_id,
                "message": error,
            },
        )

    logger.info(
        "plan_created task_id=%s subtasks=%d confidence=%s",
        plan.task_id,
        len(plan.subtasks),
        plan.metadata.confidence.value,
    )

    # Convert to dict for JSON response
    return plan.model_dump()


@app.get("/planner/versions")
async def list_planner_versions():
    """List supported planner API versions."""
    from .planner import planner_registry

    return {
        "versions": planner_registry.supported_versions(),
        "default": "1",
    }


# =============================================================================
# TASK ORCHESTRATION ENDPOINTS
# =============================================================================


@app.post("/task/create")
async def create_task(request: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Create a new task and trigger planner automatically.

    Input:
    {
        "task_id": "string",
        "objective": "string",
        "constraints": ["string"],
        "context": {...}  // optional
    }

    Returns task with planner_output_id and subtasks.
    """
    from .orchestration import task_registry
    from .supervisor import supervisor

    task_id = request.get("task_id")
    objective = request.get("objective")

    if not task_id or not objective:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_fields", "required": ["task_id", "objective"]},
        )

    # Create task
    try:
        task = task_registry.create_task(
            task_id=task_id,
            objective=objective,
            constraints=request.get("constraints", []),
            context=request.get("context"),
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"error": "task_exists", "message": str(e)})

    # Plan the task (calls /planner/plan internally)
    plan_success = await supervisor.plan_task(task)

    if not plan_success:
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "error": task.error_message,
            "planner_output_id": task.planner_output_id,
        }

    # Optionally start execution in background
    execute_async = request.get("execute", False)
    if execute_async:

        async def run_task():
            await supervisor.execute_task(task)

        background_tasks.add_task(run_task)

    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "planner_output_id": task.planner_output_id,
        "plan_hash": task.plan_hash,
        "steps": [s.to_dict() for s in task.steps],
        "message": "Task created and planned. Use /task/{task_id}/execute to run."
        if not execute_async
        else "Task execution started.",
    }


@app.get("/task/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Get task status including all subtask states.
    """
    from .orchestration import task_registry

    task = task_registry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "task_not_found", "task_id": task_id})

    return task.to_dict()


@app.post("/task/{task_id}/execute")
async def execute_task(task_id: str, background_tasks: BackgroundTasks):
    """
    Start or resume task execution.
    Runs in background, poll /task/{task_id}/status for progress.
    """
    from .orchestration import TaskStatus, task_registry
    from .supervisor import supervisor

    task = task_registry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "task_not_found", "task_id": task_id})

    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail={"error": "task_not_executable", "status": task.status.value},
        )

    # Execute in background
    async def run_task():
        await supervisor.execute_task(task)

    background_tasks.add_task(run_task)

    return {
        "task_id": task_id,
        "status": "execution_started",
        "message": "Poll /task/{task_id}/status for progress",
    }


@app.post("/task/{task_id}/approve")
async def approve_task(task_id: str, background_tasks: BackgroundTasks):
    """
    Approve a high-risk task and resume execution.
    """
    from .orchestration import TaskStatus, task_registry
    from .supervisor import supervisor

    task = task_registry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "task_not_found", "task_id": task_id})

    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "task_not_awaiting_approval",
                "current_status": task.status.value,
            },
        )

    logger.info("task_approved task_id=%s", task_id)
    _publish_transparency_event(
        event_type="decision",
        message=f"Task {task_id} approved for execution",
        correlation_id=task_id,
        task_id=task_id,
        details={
            "decision": "approved_execution_resumed",
            "status_before": task.status.value,
        },
    )

    # Transition to READY so it can be executed, and mark as approved
    task.status = TaskStatus.READY
    task.approved = True

    # Resume execution in background
    async def run_task():
        await supervisor.execute_task(task)

    background_tasks.add_task(run_task)

    return {
        "task_id": task_id,
        "status": "approved_execution_resumed",
        "message": "Task approved and execution resumed in background",
    }


@app.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """
    Cancel a task and halt all pending steps.
    """
    from .orchestration import TaskStatus, task_registry

    task = task_registry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "task_not_found", "task_id": task_id})

    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        return {
            "task_id": task_id,
            "status": task.status.value,
            "message": "Task already finished",
        }

    task.cancel()

    return {
        "task_id": task_id,
        "status": task.status.value,
        "message": "Task cancelled",
    }


@app.get("/task/list")
async def list_tasks(status: Optional[str] = None):
    """
    List all tasks, optionally filtered by status.
    """
    from .orchestration import TaskStatus, task_registry

    filter_status = None
    if status:
        try:
            filter_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_status",
                    "valid": [s.value for s in TaskStatus],
                },
            )

    tasks = task_registry.list_tasks(filter_status)

    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "objective": t.objective[:100],
                "status": t.status.value,
                "step_count": len(t.steps),
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
        "count": len(tasks),
    }


# =============================================================================
# AUDIT LOG ENDPOINTS
# =============================================================================


@app.get("/task/{task_id}/audit")
async def get_task_audit_log(task_id: str):
    """
    Get full audit log for a task.
    Returns all logged events in sequence for replay/debugging.
    """
    from audit_log import get_task_audit

    audit = get_task_audit(task_id)

    if not audit.get("events"):
        raise HTTPException(
            status_code=404,
            detail={"error": "task_not_found", "task_id": task_id},
        )

    return audit


# =============================================================================
# LOAD & CIRCUIT BREAKER ENDPOINTS
# =============================================================================


@app.get("/admin/load")
async def get_load_stats():
    """Get load statistics for all nodes."""
    from load_manager import load_manager

    return {
        "summary": load_manager.get_total_load(),
        "nodes": load_manager.get_load_stats(),
        "queues": load_manager.get_queue_stats(),
    }


@app.get("/admin/circuit-breakers")
async def get_circuit_breaker_states():
    """Get circuit breaker states for all nodes."""
    from circuit_breaker import circuit_breaker_registry

    return {
        "breakers": circuit_breaker_registry.get_all_states(),
    }


@app.post("/admin/circuit-breaker/{node_id}/open")
async def force_open_circuit(node_id: str):
    """Manually open circuit breaker for a node."""
    from circuit_breaker import circuit_breaker_registry

    circuit_breaker_registry.force_open(node_id)
    return {
        "node_id": node_id,
        "action": "opened",
        "state": circuit_breaker_registry.get_breaker(node_id).to_dict(),
    }


@app.post("/admin/circuit-breaker/{node_id}/close")
async def force_close_circuit(node_id: str):
    """Manually close circuit breaker for a node."""
    from circuit_breaker import circuit_breaker_registry

    circuit_breaker_registry.force_close(node_id)
    return {
        "node_id": node_id,
        "action": "closed",
        "state": circuit_breaker_registry.get_breaker(node_id).to_dict(),
    }


# =============================================================================
# METRICS & MONITORING ENDPOINTS
# =============================================================================


@app.get("/admin/metrics")
async def get_node_metrics():
    """Get detailed metrics for all nodes."""
    from node_metrics import metrics_registry

    return {
        "summary": metrics_registry.get_summary(),
        "nodes": metrics_registry.get_all_node_metrics(),
        "role_latency": metrics_registry.get_role_latency(),
    }


@app.get("/admin/alerts")
async def get_alerts(limit: int = 20, severity: Optional[str] = None):
    """Get recent alerts."""
    from alerting import AlertSeverity, alerting_system

    sev = None
    if severity:
        try:
            sev = AlertSeverity(severity)
        except ValueError:
            pass

    return {
        "alerts": alerting_system.get_recent_alerts(limit=limit, severity=sev),
        "counts": alerting_system.get_alert_counts(),
    }


@app.get("/admin/version")
async def get_version():
    """Get current router version info."""
    from versioning import get_current_version, version_registry

    return {
        "current": get_current_version(),
        "history": version_registry.get_history(),
    }


# =============================================================================
# MULTI-AGENT OBSERVABILITY ENDPOINTS (Phase 6)
# =============================================================================


@app.get("/admin/scheduler")
async def get_scheduler_status():
    """Get advanced scheduler status."""
    from advanced_scheduler import advanced_scheduler

    return {
        "stats": advanced_scheduler.get_queue_stats(),
        "running": advanced_scheduler.get_running_items(),
        "pending": advanced_scheduler.get_pending_items(),
        "policy": advanced_scheduler.policy.to_dict(),
    }


@app.get("/admin/state-store")
async def get_state_store_status():
    """Get shared state store status."""
    from shared_state import shared_state_store

    return {
        "stats": shared_state_store.get_stats(),
        "recent_accesses": shared_state_store.get_recent_accesses(10),
    }


@app.get("/admin/dependencies/{task_id}")
async def get_task_dependencies(task_id: str):
    """Get dependency graph for a task."""
    from dependency_graph import dependency_resolver

    try:
        order = dependency_resolver.get_subtask_order(task_id)
        return {
            "task_id": task_id,
            "execution_order": order,
            "level_count": len(order),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})


@app.get("/admin/orchestration")
async def get_orchestration_status():
    """Get full orchestration dashboard view."""
    from advanced_scheduler import advanced_scheduler
    from circuit_breaker import circuit_breaker_registry
    from load_manager import load_manager
    from shared_state import shared_state_store

    return {
        "scheduler": advanced_scheduler.get_queue_stats(),
        "state_store": shared_state_store.get_stats(),
        "load": load_manager.get_total_load(),
        "circuit_breakers": circuit_breaker_registry.get_all_states(),
    }


# =============================================================================
# EXTERNAL TOOL ENDPOINTS (Phase 7)
# =============================================================================


@app.get("/admin/tools")
async def list_tools(role: Optional[str] = None):
    """List available external tools."""
    from tools import tool_registry

    return {"tools": tool_registry.list_tools(role)}


@app.post("/admin/tools/execute")
async def execute_tool_manual(
    tool_name: str,
    inputs: Dict[str, Any],
    role: str,
    mock_trigger: bool = False,
):
    """
    Manually execute a tool (for testing).
    """
    from mock_infrastructure import TEST_SUITE
    from tools import tool_registry

    # Auto-register mocks if not present
    if mock_trigger:
        for mock in TEST_SUITE.values():
            tool_registry.register(mock)

    try:
        result = await tool_registry.execute_tool(
            tool_name=tool_name,
            inputs=inputs,
            role=role,
            task_id="manual-test",
        )
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})


# =============================================================================
# ADAPTIVE LEARNING ENDPOINTS (Phase 8)
# =============================================================================


@app.get("/admin/dashboard")
async def get_dashboard():
    """Get operational dashboard with adaptive trends."""
    from adaptive_learning import adaptive_learning
    from advanced_scheduler import advanced_scheduler
    from alerting import alerting_system
    from load_manager import load_manager

    return {
        "scheduler_queue": advanced_scheduler.get_queue_stats(),
        "load_total": load_manager.get_total_load(),
        "trends": adaptive_learning.analyze_trends(),
        "scores": adaptive_learning.get_all_scores(),
        "alerts_recent": alerting_system.get_recent_alerts(limit=5),
    }


@app.get("/admin/transparency/summary")
async def get_transparency_summary():
    """Aggregated cognitive state for dashboard bootstrap."""
    from .alerting import alerting_system
    from .autonomy_engine import autonomy_engine
    from .experiment import experiment_manager
    from .load_manager import load_manager

    active_experiments = []
    for exp in experiment_manager.get_active_experiments():
        active_experiments.append(
            {
                "id": exp.id,
                "name": exp.name,
                "status": exp.status.value,
                "variants": [v.model_dump() for v in exp.variants],
            }
        )

    return {
        "perception": perception_service.get_state(),
        "cluster": node_cache.to_dict(),
        "load": load_manager.get_total_load(),
        "alerts_recent": alerting_system.get_recent_alerts(limit=10),
        "experiments_active": active_experiments,
        "autonomy_recent": autonomy_engine.audit_log.get_logs()[-10:],
    }


@app.get("/admin/stream/decisions")
async def stream_decisions(once: bool = False):
    """Live transparency stream for routing and node-state decisions."""

    async def stream():
        queue = await transparency_stream.subscribe(replay_last=20)
        try:
            yield format_sse(
                {
                    "type": "heartbeat",
                    "message": "connected",
                    "details": {},
                }
            )
            if once:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield format_sse(event)
                except asyncio.TimeoutError:
                    pass
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    heartbeat = {
                        "type": "heartbeat",
                        "message": "alive",
                        "details": {},
                    }
                    yield format_sse(heartbeat)
                    continue
                yield format_sse(event)
        except asyncio.CancelledError:
            raise
        finally:
            await transparency_stream.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/admin/policies/suggestions")
async def get_policy_suggestions():
    """Get policy update suggestions based on trends."""
    from adaptive_learning import adaptive_learning
    from advanced_scheduler import advanced_scheduler

    trends = adaptive_learning.analyze_trends()
    current_policy = advanced_scheduler.policy
    suggestions = []

    for role, stats in trends.items():
        # Suggest increasing concurrency if high success + low latency
        if stats["success_rate"] > 95 and stats["avg_latency"] < 500:
            current_limit = current_policy.get_role_limit(role)
            suggestions.append(
                {
                    "role": role,
                    "action": "increase_concurrency",
                    "current": current_limit,
                    "suggested": current_limit + 1,
                    "reason": f"High performance (SR {stats['success_rate']}%, Lat {stats['avg_latency']}ms)",
                }
            )

        # Suggest decreasing if reliability struggling
        if stats["success_rate"] < 80:
            current_limit = current_policy.get_role_limit(role)
            if current_limit > 1:
                suggestions.append(
                    {
                        "role": role,
                        "action": "decrease_concurrency",
                        "current": current_limit,
                        "suggested": max(1, current_limit - 1),
                        "reason": f"Low reliability (SR {stats['success_rate']}%)",
                    }
                )

    return {"suggestions": suggestions}


# =============================================================================
# REFLECTION ENDPOINTS (Phase 7)
# =============================================================================


@app.post("/admin/reflection/run")
async def run_reflection_manually():
    """Trigger a manual performance reflection cycle."""
    from .reflection import reflection_engine

    report = await reflection_engine.run_reflection()
    return report


# =============================================================================
# EXPERIMENT ENDPOINTS (Phase 7)
# =============================================================================


@app.post("/admin/experiment/create")
async def create_experiment(request: Dict[str, Any]):
    """Create a new experiment."""
    from .experiment import (
        experiment_manager,
        Experiment,
        ExperimentStatus,
        ExperimentVariant,
    )

    # Simple conversion for demo/API
    variants = [ExperimentVariant(**v) for v in request.get("variants", [])]
    exp = Experiment(
        id=request.get("id", str(uuid.uuid4())),
        name=request.get("name"),
        description=request.get("description"),
        status=ExperimentStatus(request.get("status", "draft")),
        variants=variants,
        start_time=datetime.now(),
        target_roles=request.get("target_roles", []),
    )

    await experiment_manager.create_experiment(exp)
    return {"status": "created", "experiment_id": exp.id}


@app.get("/admin/experiment/active")
async def list_active_experiments():
    """List currently active experiments."""
    from .experiment import experiment_manager

    return {"experiments": [exp.dict() for exp in experiment_manager._active_experiments.values()]}


# =============================================================================
# PREDICTIVE ROUTER ENDPOINTS (Phase 9)
# =============================================================================


@app.get("/admin/predictions/stats")
async def get_prediction_stats():
    """Get pattern analysis and prediction stats."""
    from predictive_router import predictive_router
    from prefetch_manager import prefetch_manager

    return {
        "analyzer": predictive_router.analyzer.get_stats(),
        "recent_predictions": predictive_router.get_recent_predictions(),
        "prefetch_metrics": prefetch_manager.metrics,
        "config": {
            "min_confidence": prefetch_manager.min_confidence,
            "prefetch_enabled": prefetch_manager.enabled,
        },
    }


# =============================================================================
# AUTOMATED SCALING ENDPOINTS (Phase 10)
# =============================================================================


@app.get("/admin/cluster/status")
async def get_cluster_status():
    """Get full cluster status and scaling metrics."""
    from .auto_scaler import auto_scaler
    from .capabilities import capability_registry
    from .node_state import node_state_manager

    return {
        "nodes": node_state_manager.get_all_states(),
        "node_details": [info.to_dict() for info in node_state_manager._nodes.values()],
        "autoscaler": {
            "enabled": auto_scaler.enabled,
            "last_scale_event": auto_scaler.last_scale_event,
        },
        "capabilities": str(capability_registry._capabilities),  # Simplified debug view
    }


@app.post("/admin/cluster/nodes/register")
async def register_node_dynamic(
    node_id: str,
    vram_gb: int,
    capabilities: Optional[Dict[str, Any]] = None,
):
    """Dynamically register a node."""
    from cluster_manager import cluster_manager

    caps = capabilities or {}
    caps["vram_gb"] = vram_gb

    cluster_manager.register_node(node_id, caps)
    return {"status": "success", "node_id": node_id}


@app.post("/admin/cluster/nodes/deregister")
async def deregister_node_dynamic(node_id: str, reason: str = "manual"):
    """Dynamically deregister a node."""
    from cluster_manager import cluster_manager

    success = cluster_manager.deregister_node(node_id, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")

    return {"status": "success", "node_id": node_id}


# Startup event to launch background tasks


# =============================================================================
# FEDERATION ENDPOINTS (Phase 11)
# =============================================================================


@app.get("/admin/federation/peers")
async def get_federated_peers():
    """Get list of all federated clusters and their status."""
    from federation_manager import federation_manager
    from federation_router import federation_router

    return {
        "local_cluster_id": federation_manager.local_cluster_id,
        "peers": federation_manager.get_all_clusters(),
        "router_config": {
            "offload_queue_threshold": federation_router.offload_queue_threshold,
            "offload_load_threshold": federation_router.offload_load_threshold,
        },
    }


@app.post("/admin/federation/register")
async def register_federated_cluster(
    cluster_id: str,
    endpoint_url: str,
    region: str,
    capabilities: Optional[Dict[str, Any]] = None,
):
    """Register a remote cluster as a peer."""
    from federation_manager import federation_manager

    success = await federation_manager.register_cluster(
        cluster_id=cluster_id,
        endpoint_url=endpoint_url,
        region=region,
        capabilities=capabilities or {},
    )

    if not success:
        raise HTTPException(
            status_code=400, detail="Registration failed (maybe self-registration?)"
        )

    return {"status": "success", "cluster_id": cluster_id}


# Startup for federation monitor


# =============================================================================
# ADAPTIVE POLICY ENDPOINTS (Phase 12)
# =============================================================================


@app.get("/admin/policies/status")
async def get_policy_status():
    """Get active policies and adaptation metrics."""
    from adaptive_policy_engine import adaptive_engine
    from policy_manager import policy_manager

    return {
        "current_policy": policy_manager.current_policy,
        "history_count": len(policy_manager.history),
        "dry_run_mode": policy_manager.dry_run_mode,
        "metrics_trend": policy_manager.metrics.get_trend(window_minutes=5),
        "engine_enabled": adaptive_engine.enabled,
    }


@app.post("/admin/policies/rollback")
async def rollback_policy():
    """Rollback to previous policy version."""
    from policy_manager import policy_manager

    success = policy_manager.rollback()
    if not success:
        raise HTTPException(status_code=400, detail="Cannot rollback (no history)")

    return {
        "status": "success",
        "current_version": policy_manager.current_policy.version,
    }


# Startup for adaptive engine


# =============================================================================
# WORKFLOW ENDPOINTS (Phase 13)
# =============================================================================


class WorkflowCreateRequest(BaseModel):
    workflow_id: str
    steps: List[Dict[str, Any]]


@app.post("/admin/workflows/create")
async def create_workflow(request: WorkflowCreateRequest):
    """Create a new multi-agent workflow."""
    from workflow_manager import workflow_manager

    wf = workflow_manager.create_workflow(request.workflow_id, request.steps)
    return {"status": "created", "workflow_id": wf.workflow_id}


@app.get("/admin/workflows/{workflow_id}")
async def get_workflow_details(workflow_id: str):
    """Get status and steps of a workflow."""
    from workflow_manager import workflow_manager

    wf = workflow_manager.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return {
        "id": wf.workflow_id,
        "status": wf.status,
        "steps": {sid: str(s.status) for sid, s in wf.steps.items()},
        "messages": workflow_manager.get_messages(workflow_id),
    }


# Startup for workflow supervisor


# =============================================================================
# OPTIMIZATION DASHBOARD ENDPOINTS (Phase 14)
# =============================================================================


@app.get("/admin/optimization/status")
async def get_optimization_status():
    """Get workflow optimization metrics and logic status."""
    from workflow_optimizer import optimization_engine, workflow_metrics

    return {
        "metrics_count": len(workflow_metrics._metrics),
        "node_throughput": workflow_metrics.get_node_throughput(),
        "role_performance": workflow_metrics.get_role_performance(),
        "active_suggestions": optimization_engine.generate_suggestions(),
    }


@app.post("/admin/optimization/simulate")
async def simulate_optimization_strategy(strategy: Dict[str, Any]):
    """Run a dry-run simulation of an optimization strategy."""
    from workflow_optimizer import optimization_engine

    return optimization_engine.simulate_optimization(strategy)


# =============================================================================
# AUTONOMY ENDPOINTS (Phase 15)
# =============================================================================


@app.get("/admin/autonomy/logs")
async def get_autonomy_logs():
    """Get audit logs of autonomous decisions."""
    from autonomy_engine import autonomy_engine

    return autonomy_engine.audit_log.get_logs()


@app.post("/admin/autonomy/toggle")
async def toggle_autonomy(enabled: bool):
    """Enable or disable autonomous meta-task generation."""
    from autonomy_engine import autonomy_engine

    autonomy_engine.enabled = enabled
    if enabled:
        asyncio.create_task(autonomy_engine.run_loop())
    return {"status": "success", "enabled": enabled}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)

# =============================================================================
# AUDIO INTERACTION ENDPOINTS (Phase 8)
# =============================================================================


@app.post("/interaction/process_audio")
async def process_audio_interaction(audio_file: UploadFile = File(...)):
    """
    Process raw audio file (STT -> Route -> Response -> TTS).
    """
    from .interaction import interaction_manager

    audio_bytes = await audio_file.read()
    result = await interaction_manager.process_interaction(audio_in=audio_bytes)
    return result


@app.post("/interaction/process_text")
async def process_text_interaction(request: Dict[str, Any]):
    """
    Process text interaction with TTS response.
    """
    from .interaction import interaction_manager

    text = request.get("text")
    result = await interaction_manager.process_interaction(text_in=text)
    return result


@app.get("/interaction/settings")
async def get_audio_settings():
    from .interaction import interaction_manager

    return interaction_manager.config.dict()


@app.post("/interaction/settings")
async def update_audio_settings(settings: Dict[str, Any]):
    from .interaction import interaction_manager, AudioConfig

    interaction_manager.config = AudioConfig(**settings)
    return {"status": "success", "config": interaction_manager.config.dict()}
