.DEFAULT_GOAL := help

VENV := .venv

# Scripts/ on Windows, bin/ on Linux/macOS
ifeq ($(OS),Windows_NT)
    VENV_BIN    := $(VENV)/Scripts
    PYTHON_SYS  := python
else
    VENV_BIN    := $(VENV)/bin
    PYTHON_SYS  := python3
endif

PYTHON  := $(VENV_BIN)/python
PIP     := $(VENV_BIN)/pip
UVICORN := $(VENV_BIN)/uvicorn
ifeq ($(OS),Windows_NT)
    # Use 'where' (cmd.exe built-in) — avoids quoting issues and 'command -v' not existing on Windows
    _PODMAN_EXE    := $(shell where podman 2>NUL)
    _PCOMPOSE_EXE  := $(shell where podman-compose 2>NUL)
    DOCKER         := $(if $(_PODMAN_EXE),podman,docker)
    DOCKER_COMPOSE := $(if $(_PCOMPOSE_EXE),podman-compose,docker compose)
else
    DOCKER         := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null || echo docker)
    DOCKER_COMPOSE := $(shell command -v podman-compose 2>/dev/null || command -v docker-compose 2>/dev/null || echo docker compose)
endif

.PHONY: help setup backend frontend build jaeger jaeger-stop tf-init tf-plan tf-apply tf-destroy gcp-build deploy-cloud-run

help:
	@echo ""
	@echo "  make setup             Create venv and install all dependencies"
	@echo "  make backend           Start FastAPI server  →  http://localhost:8000"
	@echo "  make frontend          Start Vite dev server →  http://localhost:5173"
	@echo "  make jaeger            Start Jaeger UI    →  http://localhost:16686"
	@echo "  make build             Build frontend for production"
	@echo "  make tf-init           Initialize Terraform configuration"
	@echo "  make tf-plan           Show physical plan for Terraform changes"
	@echo "  make tf-apply          Apply Terraform configurations (auto-approve)"
	@echo "  make tf-destroy        Destroy Terraform configurations (auto-approve)"
	@echo "  make gcp-build         Build container via Google Cloud Build"
	@echo "  make deploy-cloud-run  Build container and deploy to Cloud Run in one step"
	@echo ""
	@echo "  Run jaeger, backend, and frontend in separate terminals."
	@echo ""

.env:
	cp .env.example .env
	@echo "  .env created — open it and set your GEMINI_API_KEY"

setup: .env
	$(PYTHON_SYS) -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r requirements.txt
	cd frontend && npm install
	@echo ""
	@echo "  Setup complete."
	@echo "  Terminal 1: make backend"
	@echo "  Terminal 2: make frontend"
	@echo ""

backend:
	$(UVICORN) src.server:app --reload --port 8000

frontend:
	cd frontend && npm run dev

jaeger:
	-$(DOCKER) rm -f jaeger
	$(DOCKER_COMPOSE) up -d --remove-orphans
	@echo "  Jaeger UI → http://localhost:16686"

jaeger-stop:
	$(DOCKER_COMPOSE) down --remove-orphans

build:
	cd frontend && npm run build

tf-init:
	cd terraform && terraform init

tf-plan:
	cd terraform && terraform plan

tf-apply:
	cd terraform && terraform apply -auto-approve

tf-destroy:
	cd terraform && terraform destroy -auto-approve

# ─── Docker & Cloud Run Deploy Targets ──────────────────────────────────────────
PROJECT_ID := $(shell cd terraform && terraform output -raw project_id 2>/dev/null)
REGION     := us-central1
REPO       := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/playback-iq-repo

gcp-build:
	@if [ -z "$(PROJECT_ID)" ]; then echo "Error: Run make tf-apply first to provision your GCP project."; exit 1; fi
	gcloud builds submit --tag $(REPO)/playback-iq:latest --project $(PROJECT_ID) .

deploy-cloud-run:
	@echo "================================================================="
	@echo "Phase 1: Provisioning Artifact Registry & IAM roles..."
	@echo "================================================================="
	cd terraform && terraform apply -target=google_artifact_registry_repository.repo -target=google_project_iam_member.vertex_user -target=google_project_iam_member.trace_agent -target=google_project_iam_member.metric_writer -auto-approve
	@echo "================================================================="
	@echo "Phase 2: Building and pushing container image via Cloud Build..."
	@echo "================================================================="
	$(MAKE) gcp-build
	@echo "================================================================="
	@echo "Phase 3: Deploying Cloud Run service..."
	@echo "================================================================="
	cd terraform && terraform apply -auto-approve
	@echo "================================================================="
	@echo "Phase 4: Forcing Cloud Run image refresh and rollout..."
	@echo "================================================================="
	gcloud run services update playback-iq --image $(REPO)/playback-iq:latest --project $(PROJECT_ID) --region $(REGION)

