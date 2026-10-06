# PO-In Python Agent Service

AI orchestration layer for the order-to-invoice workflow. Built with:

- **FastAPI** — API framework
- **LangChain / LangGraph** — agents and workflow orchestration
- **SQLAlchemy (async) + PostgreSQL** — persistence
- **AWS Bedrock** — document extraction / LLM (wrapped behind `bedrock_client`)
- **AWS S3** — invoice PDF storage (`bedrock_client`, `S3Client`)
- **GST/e-invoice, WhatsApp** — clients retained but currently unwired; see [Architecture](#architecture)
- **MLflow** — offline agent evaluation (`tests/evaluation`)

## Architecture

```
Router → Service → Orchestrator → Agents → Clients / Repositories
```

- Routers expose use cases only.
- Services coordinate use cases (persist run state, SQLAlchemy, S3).
- Orchestrators own compiled LangGraphs (compile at startup, invoke per use case).
- Agents perform individual workflow steps. `VerifierAgent` owns a nested graph,
  so an agent may itself be an orchestrator.
- Clients abstract external systems; repositories abstract persistence.

| Orchestrator | Module | Compiled graph |
|---|---|---|
| `POOrchestrator` | `app/orchestrator_service/po_orchestrator.py` | extraction → verification → (HITL) → sales |
| `InvoiceOrchestrator` | `app/orchestrator_service/invoice_orchestrator.py` | invoice → finalize |
| `VerifierAgent` | `app/agents/verifier_agent.py` | header / line_item / commercial → aggregate |

Shared workflow state lives in `app/orchestrator_service/graph.py`;
verification's own state is separate, in
`app/orchestrator_service/verification_state.py`, so a branch can never write to
a field it does not own.

### PO workflow

```text
START
  │
  ▼
extraction ──── failed ──────────────────────────────► END (FAILED)
  │
  ▼
verification (subgraph: header ┐
                line_item  ├─ concurrently ─► aggregate)
                commercial ┘                        │
  ├─ criteria_met ──────────────────────────────► sales ─► END
  └─ blocking ─► hitl ─┬─ APPROVE ────────────────────► sales
                       ├─ REJECT ─────────────────────► END
                       └─ EDIT ─► apply_edits ─► verification
```

`extraction` is the only node that reads the document. An `EDIT` decision
applies the correction and loops back to `verification`, never to `extraction` —
re-parsing would discard the human's change. `MAX_EDIT_ROUNDS` caps the loop.

An extraction failure terminates the run as `FAILED` with `workflow_error`
instead of raising, so the API reports a completed-with-failure run rather than
a 502.

### Verification subgraph

`VerifierAgent` is itself a compiled LangGraph. Three branches run
concurrently, each with its own prompt and its own tool allowlist, then
`aggregate` merges them:

| Branch | Tools | Owns |
|---|---|---|
| `header` | `find_customer` | **Customer identity** (`customer_id`, `customer_verified`) |
| `line_item` | `get_product`, `get_products` | Product match, quantities, line pricing |
| `commercial` | `get_applicable_policy`, `get_customer_history` | Pricing policies, deal history |

- The **header branch owns `customer_id`**. Extraction's ID is only a hint; the
  commercial branch therefore sees the hint (from which it may look up history),
  never the freshly resolved ID, because the branches run concurrently. This is
  a known coverage gap: when the customer is first resolved by the header
  branch, the commercial branch skips its history check.
- Branch agents are cached, and the subgraph is compiled once, so the graph is
  built at startup rather than per run.
- A branch that raises or returns unparsable output is isolated: it reports
  `VALIDATION_BRANCH_FAILED` and the other two still report normally. Set
  `VERIFICATION_BRANCH_FAILURE_IS_BLOCKING=false` to downgrade that to a warning.
- `blocking_issues` / `warnings` are split by issue severity. Warnings never
  block; a branch claiming `passed=true` while reporting an `error` still blocks.
- With no branch result at all, verification fails — absence is never a pass.

### Invoice workflow

```text
START → invoice → finalize → END
```

GST IRN generation and invoice message delivery are out of scope. `GSTClient`,
`generate_invoice_irn`, `MessageAgent`, and the WhatsApp tools remain in the
codebase but are not wired into any graph; `build_invoice_service_tools()`
exposes only `upload_invoice_pdf` by default.

### Configuration

Verification-specific settings:

| Setting | Default | Meaning |
|---|---|---|
| `VERIFICATION_PRICE_TOLERANCE` | `0.01` | Absolute rupee tolerance for the catalogue price comparison in line-item validation. |
| `VERIFICATION_BRANCH_FAILURE_IS_BLOCKING` | `true` | Treat an unusable validator branch as a blocking issue (HITL) instead of a warning. |

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env          # configure environment (see .env.example)
uv sync                       # install dependencies
make run                      # start dev server on :8000
```

Every setting has a default in `app/config/settings.py`; only secrets
(`JWT_SECRET`, `INTERNAL_API_KEY`, and the AWS/Bedrock keys) must be set
explicitly.

## Commands

```bash
make install     # uv sync
make run         # uvicorn dev server (reload)
make run-prod    # uvicorn prod server
make test        # pytest
make coverage    # pytest with coverage
make lint        # ruff check
make format      # ruff format
make check       # lint + format-check + test
```

## Docker

```bash
docker build -t poin-python-service .
docker run --env-file .env -p 8000:8000 poin-python-service
```

Secrets are injected at runtime via environment variables; never baked into the image.

## Logging

Stdlib `logging` only — no extra dependencies. Configured once in
`app/config/logging.py` during app startup.

```python
from app.config.logging import get_logger

logger = get_logger(__name__)
```

| Setting | Values | Meaning |
|---|---|---|
| `LOG_LEVEL` | `INFO` (default), `DEBUG`, … | Root level. `DEBUG` adds tool completions and model-call starts. |
| `LOG_FORMAT` | `text` (default), `json` | `text` is one readable line per event; `json` emits one object per line for a log shipper. |

### Message convention

One flat line per event, `key=value`, so logs are greppable by event name:

```text
quality_gate: passed=false | retry=1/3 | failed_fields=[po_number, gst_no] | breached=[po_number(score=0.41<0.75)]
tool_started: lookup_customer | agent=extraction | arg_keys=['name', 'customer_code']
llm_call: model=amazon.nova-pro-v1:0 | duration_ms=2510 | input_tokens=1420 | output_tokens=310 | stop_reason=tool_use
node_completed: verification.header | run_id=9f3c | duration_ms=812.4 | passed=true | issue_count=0
node_completed: verification.aggregate | run_id=9f3c | duration_ms=814.1 | passed=false | blocking=1 | warnings=1
node_failed: verification.commercial | run_id=9f3c | duration_ms=30012.0 | error=ReadTimeout: bedrock timeout
verification_blocked: run_id=9f3c | blocking_codes=['PRICE_VALIDATION_FAILED'] | warning_codes=[]
route: verification -> hitl | run_id=9f3c | criteria_met=false | blocking_issue_count=1
route: hitl -> sales | run_id=9f3c | decision=APPROVE | edit_rounds=0/3
```

### Levels

| Event | Level | Why |
|---|---|---|
| `agent_started` / `node_started` | INFO | Shows what is executing *right now* — a hang is visible. |
| `node_completed` | INFO | Carries `duration_ms` and the outcome. |
| `tool_started` | INFO | Tool volume is high, but the start is the live-progress signal. |
| `tool_completed` | DEBUG | `duration_ms` only; DEBUG keeps history cheap. |
| `model_call_completed` | INFO | Latency and token counts are the top debugging metric. |
| `*_failed` | ERROR | Always logged, always with a traceback. |
| `quality_gate: passed=false` | WARNING | Names the fields and the threshold each one missed. |
| `verification.<branch>` | INFO | One line per branch, so fan-out timing and a single degraded branch are both visible. |
| `verification_blocked` | WARNING | Issue **codes** only, split into blocking and warning. |

Follow a single run end to end:

```bash
grep -E "agent_started|node_started|tool_started|llm_call|quality_gate|node_completed|node_failed|verification_blocked|route" app.log | grep <run_id>
```

Branch failures are logged as `node_failed: verification.<branch>`, so a
degraded verification is attributable to a single branch rather than visible only
as a downstream HITL interruption.

### Never logged

Document bytes, full graph state, ORM objects, model prompts/responses, and tool
argument *values* — these carry customer PII and are large. Log counts, names,
durations, and booleans instead. Sensitive keys (`token`, `password`, `secret`,
`api_key`, `authorization`) are masked by `redact()` in the JSON formatter.

Verification logs issue **codes**, never issue messages: a message can quote the
document line that failed, which is customer data.

## Evaluation

`tests/evaluation/evaluate_agents.py` scores extraction field fidelity and
verification classification (`AUTO` vs `BLOCKED`) against golden fixtures in
`tests/evaluation/fixtures/`, logging to MLflow.

## API

See `app/main.py` — endpoints are served under `/api/v1`:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/agents/purchase-orders/process` | Start PO extraction + verification workflow |
| POST | `/api/v1/agents/purchase-orders/{run_id}/decision` | Submit HITL decision (APPROVE/REJECT/EDIT) |
| GET  | `/api/v1/agents/runs/{run_id}` | Get agent workflow status |
| POST | `/api/v1/internal/events/sale-delivered` | Trigger invoice workflow (Go service) |
| GET  | `/api/v1/health` | Liveness |

### Run status

| Status | Meaning |
|---|---|
| `QUEUED` | Run persisted, workflow not started. |
| `RUNNING` | Workflow in flight. |
| `WAITING_FOR_HUMAN` | Verification blocked; submit a decision via the `decision` endpoint. |
| `COMPLETED` | Finished. For PO, `sale_id` is set; for invoice, `invoice_id`. |
| `FAILED` | Terminated early. `error_code` / `error_message` carry the cause. |

A HITL response carries `hitl.question` for the reviewer plus a `hitl.context`
holding `blocking_issues` and `warnings` — the issues are split by severity so a
reviewer sees what actually stopped the run versus what merely deserves a look.

Interactive docs: `http://localhost:8000/docs`.

## Authentication

Two independent auth layers; neither is shared with the other.

### Frontend-facing APIs (Bearer JWT)

`POST /api/v1/agents/*` and `GET /api/v1/agents/runs/*` require an access
token: `Authorization: Bearer <jwt>`. Tokens are HS256-signed with
`JWT_SECRET` (shared with the Go service, which issues them during Google
sign-in). Verification lives in `app/security/token.py`; the guard is the
`get_current_user` dependency in `app/dependencies/auth.py`, which attaches
the verified identity to `request.state.user` (`AuthenticatedUser`).

- Missing / invalid / expired / wrong-signature tokens → `401 UNAUTHORIZED`.
- Optional `JWT_ISSUER` / `JWT_AUDIENCE` enforce `iss` / `aud` claims.
- `REQUIRE_AUTH=false` (dev only) lets unauthenticated requests through as
  `anonymous`; set `JWT_SECRET` in every non-dev environment.

### Internal Go → Python endpoint (service credential)

`POST /api/v1/internal/events/sale-delivered` is **not** user-authenticated.
It requires the header `X-Internal-API-Key: <key>` matching `INTERNAL_API_KEY`
(compared in constant time). The invoice workflow (Go `SALE_DELIVERED` →
invoice → S3) runs under this credential only.

`idempotency_key` is the primary duplicate guard. If it is absent or blank the
`sale_id` is used instead, and a redelivery for a sale that already has an
invoice returns that invoice rather than generating a second one.

- Missing / invalid key → `401 UNAUTHORIZED`.
- In production, calls fail closed when `INTERNAL_API_KEY` is not configured.

Feeds/contract for the event: `sale_id`, `event` (canonical `SALE_DELIVERED`;
the legacy Go `sale-delivered` spelling is accepted), `occurred_at`,
`idempotency_key`.