# AGENTS.md · knowledge-atlas

面向在本仓库工作的 AI/协作者。

## 先读什么
1. `constitution.md` — 治理原则（任务卡自动继承）
2. `spec.md` — 需求（WHAT/WHY，不谈技术栈）
3. `plan.md` — 方案 + 任务卡 + 追溯矩阵（唯一权威）
4. `status.md` — 实时进度
5. `docs/architecture.md` — 五层架构

## 分层（唐定义，勿改）
`topic 定向` → `检索层` → `拓扑层（单 namespace）` → `图谱层（多 topic 组合）` → `画像层（抽象认知习惯）`

## 硬规约
- **容器内开发**：在 `.devcontainer` 里跑，依赖用 `uv`（`uv sync` / `uv run ...`），不要用宿主 pip。
- **Python 社区规范**：`app/` 布局；`ruff`（line-length 120, py312）+ `mypy --strict` 管 `app/`；`pytest` 管 `tests/`。
- **提交前**：`make lint` 与 `make test` 必须过（与 `.pre-commit-config.yaml` 同口径）。
- **契约先行**：`tests/rag/` 的断言即契约，先读测试再实现。
- **测试默认禁网**：`tests/conftest.py` 在 `socket.connect` 层拦住一切外部连接。
  写测试时别依赖真实模型（`.env` 配了 key 时 `is_online()` 为 True，会真的发请求：
  实测整套从 0.2s 涨到 45s 且结果不稳定）。要联网请标 `@pytest.mark.allow_network`。
- **真相源**：`data/wiki/`（双链卡）与 `data/graph/edges.md` 入 git；Obsidian 本地状态不入库。
- **Git**：只 `git add` 精确文件，不自动 commit、不 push（由唐决定）。
- 与云枢 RAG **物理隔离、单向升格**。
