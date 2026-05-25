# Repository-Aware Enterprise AI Coding Agent Platform

A production-grade, secure, and private code generation and repository intelligence platform designed for internal company engineering teams.

## High-Level Architecture Overview

This platform integrates modern LLMs directly with local workspaces and organization code repositories:

1. **VSCode Extension**: Provides real-time chat, inline code generation commands, and active tab context indexing directly inside the IDE.
2. **FastAPI Backend Gateway**: Exposes token-streaming WebSockets/HTTP endpoints, indexes and queries directories, and manages sandboxed compilations.
3. **Workspace Context Engine**: Scores, filters, and ranks open files and editor selections based on logical imports and location proximity.
4. **RAG Vector pipeline**: Employs BGE embeddings stored inside a Qdrant collection to recall historical templates and projects.
5. **PEFT Fine-Tuning Module**: Feeds clean company repositories into a QLoRA adapter pipeline to align generated syntax styles without leaking logic details.
6. **LangGraph Agent Orchestrator**: Executes a multi-agent system (Planner, Retrieval, Coding, Reviewer, and Sandbox Tool Execution) to verify all code passes lint/compilation checks.

---

## Folder Layout

```
.
├── backend/
│   ├── app/
│   │   ├── api/          # Routers (Auth, Completion, Indexer)
│   │   ├── core/         # Configuration, logging, validation keys
│   │   ├── models/       # Pydantic schema contracts
│   │   └── services/     # Context, RAG, Sandbox, LangGraph, vLLM
│   ├── Dockerfile
│   └── requirements.txt
├── peft/
│   ├── config.json       # LoRA training hyperparameters
│   ├── train.py          # PyTorch fine-tuning loop script
│   └── dataset_generator.py
├── vscode-extension/
│   ├── media/            # HTML/CSS/JS Assets
│   ├── src/              # TypeScript source code
│   ├── package.json
│   └── tsconfig.json
└── docker-compose.yml    # Service orchestration (Qdrant, Postgres, Backend)
```

---

## Deployment & Setup Guide

### 1. Run Backend Services (Docker Compose)
Start Qdrant, Postgres, and the FastAPI application gateway:
```bash
docker-compose up --build -d
```

### 2. Configure vLLM Inference Server
Launch your dedicated inference server hosting Qwen2.5-Coder-32B:
```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-Coder-32B-Instruct \
    --enable-lora \
    --lora-modules enterprise-lora=/workspace/lora-enterprise-adapter \
    --port 8000
```

### 3. Compile and Run VSCode Extension
Navigate to the extension directory:
```bash
cd vscode-extension
npm install
npm run package
```
Press `F5` inside VSCode (or load the output `.vsix` bundle) to launch a new Extension Development Host window.

---

## API Documentation

- **Health Check**: `GET /health`
- **User Authentication**: `POST /api/v1/auth/login`
- **Code Indexer**: `POST /api/v1/repository/index`
- **Agent Completion Generator**: `POST /api/v1/chat/generate` (streams EventSource tokens)

---

## PEFT/LoRA Dataset Generation & Training

To adapt the model to company coding conventions, run:
```bash
# 1. Crawl source repository and parse clean docstring examples
python peft/dataset_generator.py --repo_path /path/to/enterprise/repo --output_path peft/peft_dataset.jsonl

# 2. Run LoRA training loops using PyTorch/BitsAndBytes (requires local GPUs)
python peft/train.py
```

## Security & Sandbox Rules

- **Docker Isolations**: The backend runs developer tool requests (such as linting or PyTest runs) inside isolated, non-networked containers running under low-privilege `nobody` contexts.
- **Command Sanitization**: Any terminal execution input is matched against a strict whitelist (`pytest`, `ruff`, `python`, etc.) and filtered for character injection (`&`, `|`, `;`, etc.).
- **Secret Redaction**: Response streams and execution logs are scrubbed for sensitive patterns like APIs keys, bearer tokens, or password strings.
