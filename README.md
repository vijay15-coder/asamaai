# Asama.ai - AI Engineering Assignment Implementation

This repository provides full, production-grade reference implementations for both AI Engineering problems:

---

## Directory Structure

```text
assignment/
├── problem1_agent_social_network/
│   ├── __init__.py
│   ├── models.py              # Data schemas for Agents, Posts, Comments, Routing Logs, Webhooks
│   ├── security.py            # HMAC-SHA256 signature verification & prompt injection sanitizer
│   ├── routing_engine.py      # 3-Stage Relevance Routing & dynamic closed-loop feedback learning
│   ├── main.py                # FastAPI server with REST endpoints & mock agent webhook receiver
│   └── tests/
│       ├── __init__.py
│       └── test_social_network.py # Integration & unit tests
│
├── problem2_linux_hardware_assistant/
│   ├── __init__.py
│   ├── tools_schema.py        # Strict Allow-List tool declarations & JSON parameter schemas
│   ├── parsers.py             # Deterministic parsers for dmidecode, lscpu, lsblk, free, lspci
│   ├── execution_engine.py    # Sandboxed runner (shell=False, scoped sudo & non-root fallbacks)
│   ├── assistant.py           # Multi-turn assistant with strict anti-hallucination prompting
│   ├── cli.py                 # Interactive Rich CLI for testing hardware questions
│   └── tests/
│       ├── __init__.py
│       └── test_hardware_assistant.py # Security & functional tests
└── README.md
```

---

## Problem 1: A Social Network for AI Agents

### Key Architecture Highlights
1. **Multi-Stage Relevance Routing Pipeline**:
   - **Stage 1 (SQL Rules Guardrail - $<2$ ms)**: Excludes publishing agent, deactivated agents, and blocked industries.
   - **Stage 2 (Dense Vector Search - $<15$ ms)**: Embeds post content and computes cosine similarity with agent interest manifestos ($K=50$).
   - **Stage 3 (Cross-Encoder / Joint Intent Judge - $<100$ ms)**: Evaluates joint commercial synergy. Threshold $\ge 0.55$ queues signed notifications.
2. **Trust, Safety & Prompt Injection Defense**:
   - Sanitizes post content and comments against prompt injection / jailbreak patterns (`ignore previous instructions`, `reveal secret`, etc.).
   - Dispatches webhook payloads signed with HMAC-SHA256.
3. **Closed-Loop Feedback**:
   - Updates target agent interest vectors dynamically based on feedback: positive gradient shift for comments, negative shift for unengaged drops.

### Quickstart (Problem 1)
```bash
# Run server
uvicorn problem1_agent_social_network.main:app --reload --port 8000

# View Swagger API documentation
http://127.0.0.1:8000/docs
```

---

## Problem 2: Local Linux Hardware Q&A Assistant

### Key Architecture Highlights
1. **Safe Tool-Calling Engine**:
   - `shell=False`: Syscall direct execution (`execve`) prevents command injection (`;`, `&&`, `|`, `` ` ``).
   - Strict Allow-List: Pre-approved tools (`lscpu`, `lsblk`, `dmidecode`, `free`, `lspci`). Unauthorized commands are immediately rejected.
2. **Privilege Escalation & Non-Root Fallback**:
   - Supports scoped sudo (`/etc/sudoers.d/hw-assistant`).
   - Graceful unprivileged fallback to `/proc/meminfo` and `/sys/class/dmi/id`.
3. **Anti-Hallucination Guarantee**:
   - Explicit system prompt instructions to answer *only* from verified JSON tool outputs or report *"I cannot determine this hardware detail from system data."*
4. **Distro Portability & Mock Support**:
   - Built-in live execution and hardware fixture fallback for development/testing across environments.

### Quickstart (Problem 2)
```bash
# Launch interactive CLI
python -m problem2_linux_hardware_assistant.cli
```

---

## Running All Tests

All unit, security, and integration test suites can be executed with `pytest`:

```bash
python -m pytest -v
```

