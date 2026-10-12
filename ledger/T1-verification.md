# T1 验收证据 — L1 骨架 HTML 交互图解

- 日期：2026-10-05
- 验证方式：agent-browser（真实 Chrome，经本地 HTTP `127.0.0.1:8899`，符合 runbook「UI 走真实浏览器 E2E」）
- 截图：`ledger/l1-skeleton-verified.png`

## 断言结果（全过）

| 断言 | 结果 |
|---|---|
| 节点数 = 18（1 根 + 4 支柱 + 13 叶） | ✅ |
| 边数 = 17（4 根→支柱 + 13 支柱→叶） | ✅ |
| 默认详情面板 = 根节点「Embeddings 与向量数据库」 | ✅ |
| 点击支柱「Embedding 是什么」→ 面板切换，标题/3 条要点正确 | ✅ |
| 点击后高亮 1 圆 + 5 边（1 根 + 4 叶联动） | ✅ |

## 踩坑记录
- `file://` + `--allow-file-access` 下，`open` 与后续 `eval` 落到**不同 daemon 会话**，导致读到空 body（bodyLen=0）。
- 解法：本地 `python3 -m http.server` 起 HTTP 服务再打开。**HTML 制品验证一律走 HTTP，不走 file://。**
