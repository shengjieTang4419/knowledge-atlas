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
    """可信源（L2 产物）= **平台级**：GitHub / arXiv / Oracle 官方文档 这种泛化出处。

    平台跨主题复用：搜十个主题，同一个 GitHub 仍只是一条。同一平台上的具体文件是
    `SourceEntry`（条目）——两者混在一层，攒出来的「可信源」全是一次性的，等于没有。
    """
    name: str
    type: SourceType
    why: str = ""        # 为什么这个平台可信（跨主题成立）
    home: str = ""       # 平台入口（站点 / 仓库 / 出版方）
    id: str = ""         # 归一 id（宿主域名优先，如 github.com）——条目靠它引用平台
    origin: str = "builtin"  # builtin | auto | manual

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "why": self.why,
            "home": self.home,
            "origin": self.origin,
        }


@dataclass
class SourceEntry:
    """可信源下的**具体条目**：某平台上的哪个文件 / 页面 / 章节。

    条目依附主题（arXiv 上哪篇论文，只对这个主题有意义），故挂在主题模块下，不全局注册。
    """
    title: str
    source: str = ""     # 所属平台 id（Source.id）
    locator: str = ""    # 具体定位（URL / 章节 / ISBN+页码）
    note: str = ""       # 为什么这条值得读

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "source": self.source, "locator": self.locator, "note": self.note}


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
