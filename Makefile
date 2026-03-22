.PHONY: dev dev-down api worker mcp mcp-http frontend test test-unit test-int lint format db-init db-reset install run-all wait-healthy \
	wf-prospective-scan wf-daily-maintenance wf-semantic-compression wf-relation-discovery wf-temporal-edges wf-memory-write

# --- Local services ---

dev:
	docker compose up -d

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

wait-healthy:
	@echo "Waiting for services to be healthy..."
	@for svc in dse-elasticsearch dse-neo4j dse-redis; do \
		printf "  %-20s " "$$svc"; \
		for i in $$(seq 1 60); do \
			running=$$(docker inspect --format='{{.State.Running}}' $$svc 2>/dev/null || echo "false"); \
			if [ "$$running" != "true" ]; then \
				if [ $$i -eq 60 ]; then echo "NOT RUNNING"; exit 1; fi; \
				sleep 2; continue; \
			fi; \
			health=$$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' $$svc 2>/dev/null); \
			if [ "$$health" = "healthy" ] || [ "$$health" = "running" ]; then echo "ready"; break; fi; \
			if [ $$i -eq 60 ]; then echo "TIMEOUT ($$health)"; exit 1; fi; \
			sleep 2; \
		done; \
	done
	@echo "All services healthy."

# --- Run all DSE services ---

run-all: dev install wait-healthy db-init
	@echo ""
	@echo "=== DSE is ready ==="
	@echo "Elasticsearch    : http://localhost:9200"
	@echo "Neo4j Browser    : http://localhost:7474"
	@echo "Redis            : localhost:6379"
	@echo "Temporal UI      : http://localhost:8080"
	@echo "MinIO Console    : http://localhost:9001"
	@echo "Redpanda Console : http://localhost:8085"
	@echo "API Server       : http://localhost:8000"
	@echo "MCP Server       : http://localhost:8001/mcp (streamable-http)"
	@if [ -f frontend/package.json ]; then echo "Frontend         : http://localhost:3000"; fi
	@echo ""
	@echo "Starting services... (Press Ctrl+C to stop all)"
	@echo ""
	@trap 'kill 0' EXIT; \
		cd backend && uv run uvicorn dse.main:app --host 0.0.0.0 --port 8000 --reload & \
		cd backend && uv run python -m dse.workflows.worker & \
		cd backend && uv run python -m dse.mcp --http & \
		if [ -f frontend/package.json ]; then cd frontend && pnpm install --silent && pnpm dev; fi & \
		wait

# --- Backend ---

install:
	cd backend && uv sync --all-groups

api:
	cd backend && uv run uvicorn dse.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	cd backend && uv run python -m dse.workflows.worker

mcp:
	cd backend && uv run python -m dse.mcp

mcp-http:
	cd backend && uv run python -m dse.mcp --http

# --- Frontend ---

frontend:
	cd frontend && pnpm dev

frontend-install:
	cd frontend && pnpm install

# --- Testing ---

test: test-unit

test-unit:
	cd backend && uv run pytest tests/unit -v --cov=src/dse --cov-report=term-missing

test-int:
	cd backend && USE_MOCK_LLM=true USE_MOCK_SEARCH=true uv run pytest tests/integration -v

test-all:
	cd backend && uv run pytest tests/ -v --cov=src/dse --cov-report=term-missing

# --- Code quality ---

lint:
	cd backend && uv run ruff check src/ tests/
	cd backend && uv run mypy src/dse/

format:
	cd backend && uv run ruff check --fix src/ tests/
	cd backend && uv run ruff format src/ tests/
	cd scripts && uv run ruff format ./

# --- Database ---

db-init:
	@echo "Initializing Neo4j schema..."
	cd backend && uv run python -c "import asyncio; from dse.services.graph import GraphService; asyncio.run(GraphService().init_schema())"

db-reset:
	docker compose down -v
	docker compose up -d
	$(MAKE) wait-healthy
	$(MAKE) db-init

# --- Temporal Schedules ---

register-schedules:
	cd backend && uv run python -m dse.workflows.register_schedules

register-schedules-force:
	cd backend && uv run python -m dse.workflows.register_schedules --force

# --- Trigger Workflows Manually ---
# All wf-* targets accept NS=<namespace> (default: "default")

NS ?= default

wf-prospective-scan:
	cd backend && uv run python -m dse.workflows.trigger prospective-scan --namespace $(NS)

wf-daily-maintenance:
	cd backend && uv run python -m dse.workflows.trigger daily-maintenance --namespace $(NS)

wf-semantic-compression:
	cd backend && uv run python -m dse.workflows.trigger semantic-compression --namespace $(NS)

wf-relation-discovery:
	cd backend && uv run python -m dse.workflows.trigger relation-discovery --namespace $(NS)

wf-temporal-edges:
	cd backend && uv run python -m dse.workflows.trigger temporal-edges --namespace $(NS)

wf-memory-write:
	@test -n "$(RECORD)" || (echo "Error: RECORD is required. Usage: make wf-memory-write RECORD='{\"namespace\":\"default\",\"content_text\":\"hello\"}'" && exit 1)
	cd backend && uv run python -m dse.workflows.trigger memory-write --record '$(RECORD)'
