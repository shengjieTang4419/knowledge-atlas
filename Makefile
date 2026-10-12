.DEFAULT_GOAL := help
.PHONY: help setup app app-install app-build app-check app-package view cli lint format test test-rag run clean

# ============================================================
#  knowledge-atlas
#  Python 五层（app/） + Electron 桌面端（frontend/）
#
#  ⚠ 环境边界（实测）：
#    · Python 侧  → 容器内跑（uv / ruff / mypy / pytest）
#    · 桌面窗口   → 必须在宿主 macOS 跑。Electron 是 GUI 程序，
#                   容器是 Linux VM、没有显示器，窗口弹不出来。
#    · 前端门禁   → 两边都能跑（app-check / app-build 不需要窗口）
# ============================================================

# 是否在容器内：app target 据此给出可操作的提示，而不是一句 pnpm: not found
IN_CONTAINER := $(shell [ -f /.dockerenv ] && echo 1 || echo 0)

help: ## 显示本帮助
	@echo "knowledge-atlas —— 常用命令"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "首次使用：make setup"
	@echo "启动桌面端（需宿主 macOS）：make app"

# ---------- 桌面端（Electron）----------

app: ## 启动桌面窗口 —— 必须在宿主 macOS 运行
ifeq ($(IN_CONTAINER),1)
	@echo "❌ 你在容器内，桌面窗口起不来。两层原因："
	@echo ""
	@echo "   1. Electron 是 GUI 程序，容器是 Linux VM，没有显示器接窗口；"
	@echo "   2. 容器里也没装 Node（且宿主那份 Electron 是 macOS 二进制，容器用不了）。"
	@echo ""
	@echo "   ✅ 请在【宿主 macOS 终端】执行："
	@echo "        cd ~/workSpace/study/knowledge-atlas && make app"
	@echo ""
	@echo "   ℹ️  容器内仍可跑前端门禁（不需窗口）："
	@echo "        make app-check    # 类型 + 格式"
	@echo "        make app-build    # 构建产物"
	@exit 1
endif
	@test -d frontend/node_modules || { \
		echo "❌ 前端依赖未安装，先跑：make app-install"; exit 1; }
	cd frontend && pnpm dev

app-install: ## 安装前端依赖（容器内自动跳过 Electron 二进制）
ifeq ($(IN_CONTAINER),1)
	@echo "ℹ️  容器内安装：跳过 Electron 二进制（容器显示不了窗口，用不上；省 100MB）"
	cd frontend && ELECTRON_SKIP_BINARY_DOWNLOAD=1 pnpm install
else
	cd frontend && pnpm install
endif

app-build: ## 构建桌面端产物（out/）
	cd frontend && pnpm build

app-check: ## 桌面端门禁：类型检查 + 格式检查
	cd frontend && pnpm type-check
	cd frontend && pnpm format:check

app-package: ## 打安装包（macOS dmg）—— 需在宿主运行
ifeq ($(IN_CONTAINER),1)
	@echo "❌ 打包需在宿主 macOS 运行（容器内没有 macOS 工具链）"
	@exit 1
endif
	cd frontend && pnpm build:mac

# ---------- 视图 ----------

view: ## 生成知识图谱 HTML 并打开（零依赖静态页）
	uv run python -m app.cli view
	@open deliverables/graph.html 2>/dev/null || echo "已生成 deliverables/graph.html"

cli: ## 查看 CLI 五层用法
	uv run python -m app.cli --help

# ---------- 质量门禁 ----------

lint: ## Python 门禁：ruff + mypy --strict
	uv run ruff check app/ tests/
	uv run mypy app/

format: ## Python 自动修复 + 格式化
	uv run ruff check app/ tests/ --fix
	uv run ruff format app/ tests/

test: ## 跑全部测试
	uv run pytest tests/ -v --tb=short

test-rag: ## 只跑 nanoRAG 内核契约（快）
	uv run pytest tests/rag/ -v

# ---------- 运行 ----------

run: ## 跑五层 CLI。用法：make run ARGS="orient 'Java 多线程'"
	uv run python -m app.cli $(ARGS)

# ---------- 环境 ----------

setup: ## 首次使用：装 Python 依赖（+ 前端依赖）
	uv sync
ifeq ($(IN_CONTAINER),1)
	cd frontend && ELECTRON_SKIP_BINARY_DOWNLOAD=1 pnpm install
else
	cd frontend && pnpm install
endif
	@echo "✅ 就绪。桌面窗口（需宿主）：make app"

clean: ## 清理缓存与构建产物（不动 .venv / node_modules）
	find . -type d -name __pycache__ -not -path './frontend/node_modules/*' -exec rm -rf {} + 2>/dev/null || true
	find . -type d \( -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache \) -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/out
