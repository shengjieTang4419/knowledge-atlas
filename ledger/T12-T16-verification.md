# T12–T16 验证证据 · L4 机制卡改造（一期）

## 验收结果（实测）
- **pytest**：90 passed（新增 `test_mechanism.py` 6 用例；改 `test_graph`/`test_topology`/`test_view` 借鉴→应用）
- **mypy --strict**：19 文件 0 错
- **ruff**：全过

## 端到端实测
```
uv run python -m app.cli cards
  机制卡 2 张
    · 攒批写   → InnoDB 刷盘策略、定时任务批量写
    · 失效嗅探 → MESI缓存一致性协议、分布式缓存一致性

uv run python -m app.cli analogies "InnoDB 刷盘策略"
  共享「攒批写」的同类：定时任务批量写

uv run python -m app.cli analogies "MESI缓存一致性协议"
  共享「失效嗅探」的同类：分布式缓存一致性

uv run python -m app.cli view
  实体 18（16 实体 + 2 机制卡）· 可见边 4 · 端点未建卡 3（跨域节点，设计允许）
```

## 变更清单
| 文件 | 动作 |
|---|---|
| `app/models.py` | +`MechanismCard`；`RelationType` 借鉴→应用 |
| `config/schema.yml` | +应用边 +`mechanism_card` schema；规则更新（类比非边） |
| `app/layers/mechanism.py` | 新增（load/upsert/extract/attach_cards/analogies_of） |
| `app/layers/graph.py` | judge 判「递进|无关」；attach 挂卡；write_edges 应用分区 |
| `app/layers/topology.py` | `_REL_KEYWORDS` 去借鉴；抽取 prompt 只产递进 |
| `app/cli.py` | +`cards` +`analogies` 命令 |
| `app/view.py` | 机制卡分组渲染 + 应用边 + `_norm` 小写对齐（修 pre-existing case 不一致） |
| `prompts/mechanism_extraction.md` | 新增 |
| `data/mechanism/cards.md` | 新增（2 张样例卡，迁移自原 2 条借鉴边） |
| `data/graph/edges.md` | 借鉴分区迁移为应用分区 |
| `data/wiki/notes/MESI缓存一致性协议.md` | 删借鉴行（已入「失效嗅探」卡） |
| `tests/*` | 借鉴→应用；+`test_mechanism.py` |

## 设计兑现
- 机制卡 = 一等公民（`MechanismCard` + `cards.md`），类比 = `analogies_of` 涌现查询（非边）
- 三种关系各归各：递进（graph.judge 实体↔实体）/ 应用（mechanism.attach_cards 卡↔实体）/ 类比（涌现）
