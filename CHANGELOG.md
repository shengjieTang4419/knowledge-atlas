# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 与 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.1.0] - 2026-10-12

### Changed
- **可信源拆两层**：`Source` 收窄为**平台级**（id 取宿主域名，跨主题复用、全局一份）；
  具体文件下沉为 `SourceEntry`（挂主题模块下）。旧的 `Source.locator` → `Source.home`，
  模块的 `sources` → `items`
- **平台归一治本**（`retrieve.normalize_platforms`）：按条目 `locator` 的宿主域名归并平台，
  模型列 3 篇 arXiv 论文 = 1 个可信源 + 3 条条目；无条目支撑的平台直接丢
- 内置注册表 `config/sources.yml`：`domains[].sources` → 顶层 `platforms` + `domains[].items`
- 匹配口径：平台 **id（域名）不再参与关键词匹配**（`ai` 会整词命中 `faiss.ai`）

### Added
- **搜索历史持久化**（`settings.record_search/load_history/clear_history`）：同主题只一条、上限 20、
  预演（`draft`）零副作用；侧栏「搜索」正下方展示，点了回搜该主题
- 设置页分两区：**可信源（平台）** 全局增删（内置不可删）+ **主题模块** 条目增删
- 搜索页两层展示：可信源（平台）→ 具体条目（挂平台）
- CLI：`history` / `history-clear` / `platforms` / `platform-add` / `platform-remove` /
  `entry-add` / `entry-remove`（`source-add` / `source-remove` 退役）
- 旧数据**读时迁移**：`trusted_sources` 扁平格式 → 手工模块；`sources` 混体 → 条目 + 平台（同站收敛）

## [2.0.0] - 2026-10-11

### Changed
- **L4 重构为「卡/实例两层 + 三种关系」**：机制卡（MechanismCard）升为一等公民，`借鉴` 边退役
- 关系 schema：`递进 / 借鉴` → `递进 / 应用`；类比改为「两实体共享同一张卡」的涌现查询（非边）
- `graph.judge` 只判实体↔实体的递进边，无关/跨域返回 `None`

### Added
- `app/layers/mechanism.py`：机制卡读写 / 去重合并 / 抽卡 / 挂应用边 / 类比涌现（`analogies_of`）
- `data/mechanism/cards.md`：机制卡真相源（样例：攒批写、失效嗅探）
- `prompts/mechanism_extraction.md`：抽卡判据
- CLI：`cards`（列卡）、`analogies`（查类比涌现）
- 视图：机制卡独立分组渲染 + 应用边 + `_norm` 大小写对齐
- `docs/architecture-design.html` / `docs/architecture-review.html`：架构设计交互图解

### Removed
- `借鉴` 边：`edges.md` 借鉴分区迁移为应用分区；`MESI缓存一致性协议` 卡的借鉴行删除

## [1.0.0] - 2026-10-07

### Added
- 五层骨架：`app/layers/{topic,retrieve,topology,graph,profile}.py` + `递进/借鉴` 两条边
- nanoRAG 内核：`app/rag/{chunker,bpe,embed,fuse}.py` + 契约测试 `tests/rag/`
- 领域类型：`app/models.py`（Source / Entity / Relation / Namespace / Edge / Profile）
- Electron 薄壳 + Vue3 桌面端（壳无脑、脑在 `app/`）
- LLM 客户端（OpenAI 兼容）+ 离线降级
- 四级可信源查找 + 模块即缓存（`config/sources.yml` / `data/settings/settings.json`）
- 容器内开发：`.devcontainer/` + uv + ruff + mypy(strict) + pre-commit + Makefile
