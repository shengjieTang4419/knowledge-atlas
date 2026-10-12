# knowledge-atlas · Personal Knowledge Platform

Give a topic → find trusted sources → build a single-namespace topology → extract **mechanism cards** and attach them to a cross-topic graph → profile feeds back.

## Five Layers

```
L1 topic orientation → L2 retrieval → L3 topology (single namespace) → L4 graph (multi-topic) → L5 profile
```

## Core Idea: Card/Instance Two Layers + Three Relations (v2)

A **mechanism card** abstracts the transferable "solution action" out of its context.

| Relation | What it is | Example |
|---|---|---|
| `递进` (is-a/contains) | entity ↔ entity, objective hierarchy | `juc → jvm → jmm` |
| `应用` (applies-to) | card ↔ entity, anchors abstraction to practice | `TCC 卡 → 订单预扣` |
| analogy | **emergent, not an edge** — two entities sharing one card | `InnoDB 刷盘 ↔ 定时任务批量写` |

The mechanism card decides the *height* of the network (the "golden threads"); `is-a` + `applies-to` decide its *density*.

## Layout

```
knowledge-atlas/
├── app/
│   ├── models.py          # Source / Entity / Relation / Namespace / Edge / MechanismCard / Profile
│   ├── cli.py             # thin entry
│   ├── layers/            # topic · retrieve · topology · graph · mechanism · profile
│   ├── rag/               # nanoRAG kernel: chunker · bpe · embed · fuse
│   ├── llm.py             # OpenAI-compatible client + offline fallback
│   └── view.py            # data/ → single-file HTML graph
├── config/                # sources.yml · schema.yml
├── prompts/               # sourcing · extraction · relation_typing · mechanism_extraction
├── data/                  # wiki/ (double-linked cards) · graph/edges.md · mechanism/cards.md
├── docs/                  # architecture.md · architecture-design.html · architecture-review.html
├── frontend/              # Electron thin shell + Vue3
├── tests/                 # mirrors app/
└── constitution / spec / plan / status / CHANGELOG / ledger
```

## ⚠ Environment Boundary (read first)

| Task | Where | Why |
|---|---|---|
| Python layers (lint / test / CLI / view) | **inside devcontainer** | uv / ruff / mypy / pytest live there |
| Frontend gates (type-check / build) | inside container | no window needed |
| Desktop window (`make app`) | **host macOS only** | Electron is a GUI app; the container is a Linux VM |

## AI Config (optional)

```bash
cp .env.example .env   # fill LLM_API_KEY / LLM_BASE_URL
```

`.env` is auto-loaded by `app/config.py` (never overrides exported vars). Without it, everything degrades to offline/deterministic paths.

## Run (inside devcontainer)

```bash
make lint        # ruff + mypy --strict
make test        # pytest
make test-rag    # nanoRAG kernel contracts only
make dev         # CLI help
make run ARGS="orient 'Java 多线程'"
```

## View the Graph

```bash
uv run python -m app.cli view          # -> deliverables/graph.html (open in browser)
uv run python -m app.cli cards         # list mechanism cards
uv run python -m app.cli analogies "InnoDB 刷盘策略"   # emergent analogies
```

## Desktop (Electron thin shell)

From the **host macOS** terminal (not the container):

```bash
make app   # = cd frontend && pnpm dev
```

## Status

See `status.md`.
