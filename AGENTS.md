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

---

## 〇、AI 协作准则（新增功能必考量）

- **无非必要，不增实体**：每新增接口 / 模块 / 文件 / 类，先回答「删掉它谁会受影响」；答不出就不加。
- **YAGNI**：不写猜测性代码。判据与实测见 `~/.dsh/AGENTS.md` §二·五，此处不重复。
- **治本优先于补丁**：先钉死根因再动手，不接受用数据补丁或临时包装冒充修复。
- **正确性优先于吞吐**：真相源写盘、跨层契约宁可多一次校验，不可省。
- **取舍留注释**：非常规写法（降级路径、stub 身份、`# type: ignore`）旁边写明理由。

## 一、分层职责（薄入口）

- **入口层只做两件事**：① 绑定（CLI 子命令 / IPC 通道 → 调用）② 结构转化（请求解析、响应包装）。
  入口 = `app/cli.py`（薄入口）+ `frontend/src/main/ipc.ts`（薄壳）。
- **带判断的业务逻辑一律下沉 `app/layers/`**（过滤、默认值、校验、规则、跨层编排的判断）。
  入口里出现带判断的业务代码，属评审必改项。
- **renderer 不做业务计算**：数据一律由主进程从 `data/` 读、或调 Python CLI 取
  （契约见 `frontend/src/shared/ipc.ts` 头部）。
- 层间只经 `app/models.py` 的骨架类型通信；层边界见 `docs/architecture.md`。

## 二、类型注解与 `Any` 判据（门禁）

**门禁**（本地 = pre-commit 同一口径，勿绕）：`make lint`（`ruff check app/ tests/` + `mypy --strict app/`）。
**改完先跑，红了不算完成。**

`Any` 只有两种允许情形，其余一律写实：

| 允许 | 判据 | 本仓例 |
|---|---|---|
| ① 外部 JSON / 配置边界 | 结构由外部（模型输出、`settings.json`、`config/*.yml`）决定，本进程无法也不应穷举 | `chat_json(...) -> dict[str, Any]`、`load_sources() -> dict[str, Any]` |
| ② 第三方无 stub | 库未提供 `py.typed`，用 mypy override 收口，而非撒 `# type: ignore` | 当前无（`types-pyyaml` 已装） |

**明确不许**（这几类曾真实把缺陷藏住）：

- ❌ 工厂 / 回调的返回类型写 `Any` → 写实返回类型；
- ❌ 成员变量写 `Any`（`self._x: Any`）→ 精确类型或 `X | None`；
- ❌ `dict` / `list` 裸泛型（mypy `type-arg` 会拦）→ 至少补 `dict[str, Any]`。

判据一句话：`Any` 是在声明「**我放弃检查这里**」——只有确实无权 / 无法约束时才用。

两个坑：仅作注解的导入放 `if TYPE_CHECKING:`（ruff TC00x）；注解写实类型，别用字符串 / `getattr` 绕门禁。

## 三、Electron 主进程 · 别阻塞

主进程是**单线程事件循环**：IPC handler 里不许出现**重**同步阻塞
（用 `execFile` 不用 `execFileSync`；重 IO 走异步 API）。

判据与 x_ai 同源：**耗时 >> 调度开销（几十微秒）才异步**——毫秒级小文件读写（< 5ms）同步即可，别过度包装。

> x_ai 那套 `async def` 铁律（换 async 库 / `asyncio.to_thread`）**面向异步 Web 服务，本仓不适用**：
> Python 侧是同步 CLI，没有事件循环，套过来只增复杂度。

## 四、代码风格

- 类型注解明确；`typing.Dict/List` 已弃用，直接写 `dict/list`。
- 导入分组：标准库 → 第三方 → 本地，组内字母序（ruff `I001`）。
- 中文注释；docstring 只在类 / 模块级写几句职责，方法靠命名自解释——**不复述「是什么」，只写「为什么」**。
- 提交署名 `shengjie.tang`（`small` 是同事，禁署）。

## 五、硬规约

- **容器内开发**：在 `.devcontainer` 里跑，依赖用 `uv`（`uv sync` / `uv run ...`），不要用宿主 pip。
- **Python 社区规范**：`app/` 布局；`ruff`（line-length 120, py312）+ `mypy --strict` 管 `app/`；`pytest` 管 `tests/`。
- **提交前**：`make lint` 与 `make test` 必须过（与 `.pre-commit-config.yaml` 同口径）。
- **契约先行**：`tests/rag/` 的断言即契约，先读测试再实现。
- **测试默认禁网**：`tests/conftest.py` 在 `socket.connect` 层拦住一切外部连接。
  写测试时别依赖真实模型（`.env` 配了 key 时 `is_online()` 为 True，会真的发请求：
  实测整套从 0.2s 涨到 45s 且结果不稳定）。要联网请标 `@pytest.mark.allow_network`。
  需要确定性离线路径时用 `app.llm.set_offline(True)` 显式关掉。
- **真相源**：`data/wiki/`（双链卡）与 `data/graph/edges.md`、`data/mechanism/cards.md` 入 git；
  Obsidian 本地状态不入库。写盘必须**幂等**、且**不覆盖人工已写的内容**。
- **模型资源事实在配置里，业务代码里不许出现厂商名 / 模型名 / `base_url`**（曾写死 `qwen-flash`
  而后在网关上 403——写死即绕过配置）。**配置在界面上改**（右下角 ⚙ → 模型），落 `data/settings/llm.json`（不入 git）；
  `.env` 只做**播种**——文件一旦存在即为唯一真源。换模型、加一家 = 在界面上改，零代码。
  失败按链**有界降级**且**必须可见**（`last_llm_route` / `last_llm_degraded`）——静默降级等于没降级。
- **明文凭据不回传界面**：读接口只给 `hasKey` + 脱敏提示，故保存时「留空 = 不改」；
  凭据优先用 `apiKeyEnv` 引用环境变量，**密钥不落盘**。
- **Git**：只 `git add` 精确文件，不自动 commit、不 push（由唐决定）。
- 与云枢 RAG **物理隔离、单向升格**。

## 六、收尾清单（功能做完逐条过）

- [ ] **门禁全绿**：`make lint` + `make test`；动了前端再加 `make app-check`（必要时 `make app-build`）
- [ ] **薄入口**：入口层没有带判断的业务逻辑
- [ ] **最小实体**：新加的每个实体都答得出「删掉它谁会受影响」
- [ ] **无虚假契约**：接口 / JSON 字段都有实现真正用上
- [ ] **测试补齐且离线可跑**：不依赖真实模型
- [ ] **写入幂等**：`data/` 重复写不重复、不覆盖人工内容
- [ ] **文档同步**：`plan.md` 任务卡 + `status.md` 当前态只表达**当前架构**，不写改造史
- [ ] **只 `git add` 精确文件**（不自动 commit / push）
