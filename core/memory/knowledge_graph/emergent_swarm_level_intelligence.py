# Title: Emergent Swarm-Level Intelligence


def compute_swarm_metrics(swarm):
    role_counts = {
        role: 0 for role in ["Researcher", "Analyst", "Creative Coder", "Communicator", "Explorer"]
    }
    for agent in swarm.agents:
        role_counts[agent.role] += 1
        # optionally, compute node coverage per agent if tracking KG locally
    # Detect role gaps
    min_role = min(role_counts, key=role_counts.get)
    return {"role_counts": role_counts, "least_role": min_role}


def assign_task_with_swarm_strategy(agent, swarm):
    # Compute emergent task scores
    swarm_metrics = compute_swarm_metrics(swarm)
    tasks = ["exploration", "validation", "experiment", "communication"]
    scores = []
    for t in tasks:
        score = 0
        if t == "exploration" and "curious" in agent.profile.get("personality traits", []):
            score += 1
        if t == "validation" and "analytical" in agent.profile.get("personality traits", []):
            score += 1
        if t == "experiment" and "creative" in agent.profile.get("personality traits", []):
            score += 1
        if t == "communication" and "social" in agent.profile.get("personality traits", []):
            score += 1
        # Emergent swarm need: prioritize tasks for underrepresented role
        if t == "exploration" and swarm_metrics["least_role"] == "Explorer":
            score += 1
        scores.append((t, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[0][0]
