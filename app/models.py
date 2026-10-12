"""核心领域类型（骨架契约）。

五层共享的类型，先钉死；L1–L5 都依赖它。字段只保留「骨架级」，细节留待功能开发。
"""
from dataclasses import dataclass, field
from typing import Any, Literal

# 关系类型：递进 = 竖·深度（is-a/contains 骨架，实体↔实体）；应用 = 锚点（机制卡↔实体）。
# 类比不再是边：它是两个实体共享同一张机制卡的涌现关系（见 app/layers/mechanism.py）。
RelationType = Literal["递进", "应用"]

# 可信源类型（L2 可信度分级：规范·源码最高 → 社区最低）
SourceType = Literal["规范", "源码", "书籍", "论文", "博客", "社区"]


@dataclass
class Source:
    """可信源（L2 产物）。"""
    name: str
    type: SourceType
    why: str = ""        # 为什么可信
    locator: str = ""    # 链接 / 定位 / clone 方式


@dataclass
class Entity:
    """实体（L3 产物）。"""
    name: str
    type: str = "概念"   # 概念 / 机制 / 产品 / 规范 / 人物
    one_line: str = ""


@dataclass
class MechanismCard:
    """机制卡（L4 一等公民）：把可迁移的「解法动作」从语境中抽象出来。

    name 用动词锚定（如「攒批写」「削峰填谷」），不用名词——名词会糊、动词才可迁移。
    """
    name: str
    problem: str = ""        # 解决什么形态的问题（不是解决什么业务）
    mechanism: str = ""      # 核心动作（动词结构，一句话）
    tradeoff: str = ""       # 付出什么代价
    boundary: str = ""       # 什么时候不该用
    cases: list[str] = field(default_factory=list)  # 已挂实例（实体名清单）


@dataclass
class Relation:
    """关系边（L3 领域内 / L4 跨领域共用）。"""
    src: str
    dst: str
    type: RelationType


@dataclass
class Namespace:
    """单 topic 拓扑（L3 产物）。"""
    topic: str
    sources: list[Source] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)


@dataclass
class Edge:
    """全局图谱边（L4 产物）。"""
    src: str
    dst: str
    type: RelationType
    confidence: str = "high"   # high | low（low = 待复核，不进图谱）
    reason: str = ""


@dataclass
class Profile:
    """认知习惯画像（L5 产物）。"""
    preferences: dict[str, Any] = field(default_factory=dict)
