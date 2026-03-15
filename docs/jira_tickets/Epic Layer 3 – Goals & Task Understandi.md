Epic: Layer 3 – Goals & Task Understanding

Objective: Develop the system’s ability to interpret, decompose, and manage tasks from user input and external events, ensuring tasks are context-aware, prioritized, conflict-free, and assignable to agents.

Jira Tickets

1. Task Parser Implementation

Description: Build a parser to interpret user commands, environment inputs, and system events. Ensure it supports context-aware parsing using current state and memory.

Acceptance Criteria:

Input text, speech, or event is parsed into structured tasks.

Parser integrates with Context Builder and Memory System to maintain situational awareness.

Test cases include ambiguous inputs and multi-intent commands.

Subtasks:

Integrate context retrieval from Memory (KG, Vector Store, Working Memory).

Implement NLP module for intent and entity extraction.

Test parser with multi-turn inputs.

2. Task Decomposition Engine

Description: Decompose high-level tasks into actionable sub-tasks for downstream execution.

Acceptance Criteria:

Tasks are broken into discrete steps with dependencies.

Each sub-task retains links to original intent and context.

Compatible with multi-agent assignment.

Subtasks:

Define decomposition rules based on task type.

Create dependency graph structure for sub-tasks.

Validate decomposition using sample commands.

3. Goal / Mission Manager

Description: Manage the lifecycle of goals, including tracking progress, dependencies, and status updates.

Acceptance Criteria:

Goals are prioritized based on importance and urgency.

Conflicting tasks are detected and resolved.

Supports reassignment to multiple agents if needed.

Subtasks:

Implement priority scoring algorithm based on goal metadata and system state.

Implement conflict resolution rules to handle competing tasks.

Integrate with Scheduler/Orchestrator for agent assignment.

4. Context-Aware Task Enhancements

Description: Extend parser and decomposition with context awareness, improving understanding of ambiguous or incomplete tasks.

Acceptance Criteria:

Tasks adapt dynamically based on Memory and World Model feedback.

Historical context influences task prioritization and sub-task creation.

Subtasks:

Integrate Memory and World Model feedback loops.

Implement fallback logic for unclear or incomplete tasks.

Validate with multi-turn scenario testing.

5. Multi-Agent Assignment & Coordination

Description: Enable tasks to be assigned to one or more agents in the swarm efficiently.

Acceptance Criteria:

Each task is mapped to capable agents from Agent Swarm layer.

Load balancing ensures no agent is overloaded.

Conflicts between agent assignments are detected and resolved automatically.

Subtasks:

Define agent capabilities and mapping logic.

Integrate with Orchestrator and Scheduler.

Implement assignment validation using sample tasks.