# Observability Stack

The **Observability** layer (`observability/`) provides real-time insights into the health, cost, and efficiency of the Raphael swarm network.

## Components

The stack relies on three main tools:
1. **OpenTelemetry (OTel)**: Embedded within the Python agents (`observability/telemetry.py`) to provide deep distributed tracing of LLM logic and reasoning chains.
2. **Prometheus**: Scrapes numerical metrics from the Swarm Director and running Habitats (e.g., active pods, queue depth, token usage).
3. **Grafana**: Visualizes the Prometheus metrics via pre-provisioned dashboards.

## Dashboards

Dashboards are automatically mapped within `observability/grafana/dashboards/`:

### Habitat Metrics
Visualizes the performance bounds of the Swarm.
- **Task Completion Rate**: Success vs Failure ratio of deployed habitats answering requests.
- **Agent Success Rates**: The internal efficiency of specific agents (Planner vs Coder) inside the ephemeral habitats.
- **Queue Depth**: The current load on the `TaskManager`.

## Configuration

The Director automatically provisions the Grafana datasources (`datasource.yaml`) and dashboards (`dashboard.yaml`) on startup via the `Makefile` bootstrapper. Custom metrics can be added directly to `habitat_metrics.json` and will load immediately on restart.
