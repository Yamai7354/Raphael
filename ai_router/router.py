"""
Router Module for AI Router.

Provides routing logic with hard guardrails to ensure requests
only go to READY nodes. Fails fast and explicitly when no
suitable nodes are available.
"""

import logging
import asyncio  # Added import
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from .state_cache import node_cache
from core.understanding.schemas import Task
from .policy import policy_registry
from event_bus.event_bus import Event
from . import bus  # Import singleton
from .perception import perception_service
from .resource import resource_manager
from .experiment import experiment_manager
from .transparency_stream import transparency_stream

logger = logging.getLogger("ai_router.router")


class RouterError(Exception):
    """Base exception for routing errors."""

    pass


class NoReadyNodesError(RouterError):
    """Raised when no READY nodes are available for the requested role."""

    pass


class RoleMismatchError(RouterError):
    """Raised when no nodes match the requested role."""

    pass


async def get_ready_nodes_for_role(
    role: Optional[str], config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get all READY nodes that match the specified role.
    If role is None or doesn't match any infrastructure role, return all READY nodes.

    Raises:
        NoReadyNodesError: If no READY nodes are available.
    """
    # CRITICAL CHANGE: Use cache as source of truth for ALL nodes (static + dynamic)
    all_nodes = node_cache.get_all_nodes_as_dicts()
    ready_nodes = node_cache.get_ready_nodes()  # Set of IDs

    if not ready_nodes:
        logger.error("routing_failed reason=no_ready_nodes")
        raise NoReadyNodesError("No READY nodes available in the cluster")

    # Get all READY nodes first
    all_ready = [node for node in all_nodes if node["id"] in ready_nodes]

    # If no role specified, return all READY nodes
    if role is None:
        return all_ready

    # Check if role matches any node's infrastructure role
    # Known infrastructure roles: fast_inference, heavy_inference
    matching_nodes = [
        node
        for node in all_nodes
        if node["id"] in ready_nodes and node.get("role") == role
    ]

    # filter out overloaded nodes
    available_nodes = []
    for node in matching_nodes if matching_nodes else all_ready:
        if await resource_manager.can_accept_task(node["id"]):
            available_nodes.append(node)

    if not available_nodes:
        logger.warning(f"All READY nodes for role {role} are currently overloaded.")
        # We could either raise an error or return the least loaded.
        # For MVP, we raise NoReadyNodesError (which translates to 503)
        raise NoReadyNodesError(f"No available nodes for role {role} (all overloaded)")

    return available_nodes


async def select_node(role: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Select the best READY node for a request.
    Currently uses simple lowest-latency selection.

    Returns the selected node configuration.

    Raises:
        NoReadyNodesError: If no READY nodes are available.
        RoleMismatchError: If no nodes match the specified role.
    """
    candidates = await get_ready_nodes_for_role(role, config)

    # Select by highest score (Success Rate + Latency)
    best_node = None
    best_score = -1.0
    best_latency = float("inf")

    for node in candidates:
        node_info = node_cache.get_node(node["id"])
        if node_info:
            score = node_info.score
            if score > best_score:
                best_score = score
                best_node = node
                best_latency = (
                    node_info.latency_ms
                    if node_info.latency_ms is not None
                    else float("inf")
                )

    if best_node is None:
        # Fallback should technically not happen if candidates exist and are in cache
        best_node = candidates[0]

    logger.info(
        "routing_decision node_id=%s role=%s score=%.2f latency_ms=%s",
        best_node["id"],
        best_node.get("role"),
        best_score,
        best_latency if best_latency != float("inf") else "unknown",
    )
    asyncio.create_task(
        transparency_stream.publish(
            {
                "type": "decision",
                "node_id": best_node["id"],
                "message": "Routing guardrail selected node",
                "details": {
                    "role": role,
                    "score": best_score,
                    "latency_ms": best_latency
                    if best_latency != float("inf")
                    else None,
                    "source": "routing_guardrail",
                },
            }
        )
    )

    return best_node


async def select_node_for_task(task: Task, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Select the best READY node for a specific Task.
    Extracts routing constraints (role, model, assignment) from the Task object.

    Priority:
    1. Direct Assignment (task.assigned_to matching a node ID)
    2. Role-based routing (task.agent_config["role"])
    3. Model-based routing (task.agent_config["model"])
    4. Default/Fallback
    """

    # 0. Risk Evaluation (Autonomous Risk Modeling)
    perception_state = perception_service.get_state()
    risk_score = policy_registry.validator.evaluate_task_risk(task, perception_state)
    logger.info(
        f"routing_risk_eval task={task.id} risk={risk_score.value} context={perception_state}"
    )

    # 1. Direct Assignment
    if task.assigned_to:
        # Check if assigned_to is a valid node ID
        all_nodes = node_cache.get_all_nodes_as_dicts()
        for node in all_nodes:
            if node["id"] == task.assigned_to:
                # Check if ready
                if node["id"] in node_cache.get_ready_nodes():
                    logger.info(
                        f"routing_decision source=assignment task={task.id} node={node['id']}"
                    )
                    return node
                else:
                    logger.warning(
                        f"task={task.id} assigned to {task.assigned_to} but node is NOT READY. Falling back."
                    )

    # 2. Extract Role / Model from agent_config
    role = task.agent_config.get("role")
    model = task.agent_config.get("model")

    # Get candidates based on role first
    try:
        candidates = await get_ready_nodes_for_role(role, config)
    except NoReadyNodesError:
        logger.error(
            f"routing_failed task={task.id} reason=no_ready_nodes_for_role role={role}"
        )
        raise

    # 3. Filter by Model Capability (if specified)
    if model:
        from .capabilities import capability_registry

        filtered = []
        for node in candidates:
            caps = capability_registry.get_capabilities(node["id"])
            # If caps are loaded and node has the model
            if caps and caps.can_host_model(model):
                filtered.append(node)
            elif not caps:
                # If no Capabilities registered, we filter it out to be safe for explicit model requests
                pass

        if filtered:
            candidates = filtered
            logger.info(
                f"routing_filter task={task.id} model={model} remaining_nodes={len(candidates)}"
            )
        else:
            logger.warning(
                f"routing_filter_fail task={task.id} model={model} reason=no_nodes_host_model. Ignoring model constraint."
            )

    # 4. Handle Experiments (Phase 7)
    weights = {"success_weight": 0.7, "latency_weight": 0.3}
    active_exps = experiment_manager.get_experiments_for_task(task)
    experiment_id = None
    variant_id = None

    if active_exps:
        # For now, we only support one active experiment per task
        exp = active_exps[0]
        variant = await experiment_manager.assign_variant(exp, task)
        experiment_id = exp.id
        variant_id = variant.id
        # Override weights if provided in variant config
        if "success_weight" in variant.config:
            weights["success_weight"] = variant.config["success_weight"]
        if "latency_weight" in variant.config:
            weights["latency_weight"] = variant.config["latency_weight"]
        logger.info(
            f"experiment_active id={experiment_id} variant={variant_id} weights={weights}"
        )

    # 5. Select Best Node (Highest Score)
    best_node = None
    best_score = -1.0
    best_latency = float("inf")

    for node in candidates:
        node_info = node_cache.get_node(node["id"])
        if node_info:
            # Use weights from experiment or defaults
            score = node_info.calculate_score(**weights)
            if score > best_score:
                best_score = score
                best_node = node
                best_latency = (
                    node_info.latency_ms
                    if node_info.latency_ms is not None
                    else float("inf")
                )

    if best_node is None:
        best_node = candidates[0]

    logger.info(
        "routing_decision task=%s node_id=%s role=%s model=%s score=%.2f latency_ms=%s experimental=%s",
        task.id,
        best_node["id"],
        role,
        model,
        best_score,
        best_latency if best_latency != float("inf") else "unknown",
        "yes" if experiment_id else "no",
    )
    asyncio.create_task(
        transparency_stream.publish(
            {
                "type": "decision",
                "correlation_id": task.id,
                "task_id": task.id,
                "node_id": best_node["id"],
                "message": "Routing decision computed",
                "details": {
                    "role": role,
                    "model": model,
                    "risk_score": risk_score.value,
                    "score": best_score,
                    "latency_ms": best_latency
                    if best_latency != float("inf")
                    else None,
                    "experiment_id": experiment_id,
                    "variant_id": variant_id,
                },
            }
        )
    )

    # Publish routing event (fire and forget)
    if bus.event_bus:
        asyncio.create_task(
            bus.event_bus.publish(
                Event(
                    topic="task.routed",
                    payload={
                        "task_id": task.id,
                        "node_id": best_node["id"],
                        "role": role,
                        "model": model,
                        "risk_score": risk_score.value,
                        "source": "router",
                        "score": best_score,
                        "latency_ms": best_latency
                        if best_latency != float("inf")
                        else None,
                        "experiment_id": experiment_id,
                        "variant_id": variant_id,
                    },
                    correlation_id=task.id,
                )
            )
        )

    return best_node


async def routing_guardrail(
    role: Optional[str], config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for routing with guardrails.
    Fails fast with clear HTTP errors if routing is not possible.

    Returns the selected node configuration.

    Raises:
        HTTPException: With appropriate status code and error message.
    """
    try:
        return await select_node(role, config)
    except NoReadyNodesError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no_ready_nodes",
                "message": str(e),
                "action": "retry_later",
            },
        )
    except RoleMismatchError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "role_mismatch",
                "message": str(e),
                "action": "check_config",
            },
        )
