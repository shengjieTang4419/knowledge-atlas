"""五层（唐定义的顺序，勿改）。

| 模块 | 层 | 职责 | 输入 → 输出 |
|---|---|---|---|
| `topic`    | L1 topic 定向      | 主题拆检索词         | str → list[str] |
| `retrieve` | L2 检索层          | 找可信源（平台 + 条目） | keywords → list[Source] + list[SourceEntry] |
| `topology` | L3 拓扑层          | 单 namespace 拓扑    | sources → Namespace |
| `graph`    | L4 图谱层          | 多 topic 组合成图谱  | Namespace → list[Edge] |
| `profile`  | L5 画像层          | 抽象认知习惯         | events → Profile |

L4 是价值层：cosine 召回（哪些相关）+ LLM 判边（什么关系：递进/借鉴）。
"""
