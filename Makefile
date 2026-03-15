.PHONY: test test-with-services

test:
	./scripts/test.sh -- $(TEST_ARGS)

test-with-services:
	./scripts/test.sh --with-services -- $(TEST_ARGS)

# Default variables for agent building
DOCKER_REGISTRY ?= ttl.sh/raphael-swarm
VERSION ?= 1h

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build-agents: ## Build Docker images for Planner and Coder agents
	@echo "Building Agent Docker images..."
	docker build -t $(DOCKER_REGISTRY)/planner-agent:$(VERSION) -f docker/planner-agent.Dockerfile .
	docker build -t $(DOCKER_REGISTRY)/coding-agent:$(VERSION) -f docker/coding-agent.Dockerfile .
	@echo "Pushing images to ephemeral registry for k3d..."
	docker push $(DOCKER_REGISTRY)/planner-agent:$(VERSION)
	docker push $(DOCKER_REGISTRY)/coding-agent:$(VERSION)

run-dev: ## Bootstrap the local environment (Neo4j, NATS, Director)
	@echo "Installing dependencies..."
	pip install -e .
	@echo "Starting Swarm Director in development mode..."
	python director/swarm_director.py

lint: ## Run Ruff for code linting and formatting
	ruff check .
	ruff format .

clean: ## Clean up Python cache files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
