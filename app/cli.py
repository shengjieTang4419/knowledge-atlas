"""薄入口：只做参数解析与分层调用，不写业务（业务在 layers/）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal

from app import llm, settings, view
from app.layers import graph, mechanism, profile, retrieve, topic, topology
from app.models import Edge, Entity, MechanismCard, Namespace, Relation, Source, SourceEntry


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="knowledge-atlas",
        description="个人知识学习平台（五层：topic 定向 / 检索 / 拓扑 / 图谱 / 画像）",
    )
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("orient", help="L1 topic 定向：主题 -> 关键词")
    s.add_argument("topic")

    s = sub.add_parser("sources", help="L2 检索层：关键词 -> 可信源清单")
    s.add_argument("topic", help="主题（内部先做 L1 定向）")
    s.add_argument("--limit", type=int, default=5)

    s = sub.add_parser("topology", help="L3 拓扑层：可信源 -> 单 namespace 拓扑")
    s.add_argument("topic", nargs="?", default="", help="留空 = 读全部现有 wiki")
    s.add_argument("--json", action="store_true", help="输出 JSON")

    s = sub.add_parser("attach", help="L4 图谱层：新 namespace -> 挂进全局图谱")
    s.add_argument("topic", nargs="?", default="", help="留空 = 用全部现有 wiki")
    s.add_argument("--top-k", type=int, default=5)
    s.add_argument("--min-score", type=float, default=graph.DEFAULT_MIN_SCORE)
    s.add_argument("--dry-run", action="store_true", help="只算不写盘")

    s = sub.add_parser("profile", help="L5 画像层：学习行为 -> 认知习惯")
    s.add_argument("--record", action="store_true", help="记录一条事件而非汇总")
    s.add_argument("--topic", default="")
    s.add_argument("--action", default="")

    s = sub.add_parser("cards", help="L4 机制卡：列出机制卡库")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("analogies", help="L4 类比：查某实体共享机制卡的同类实体（涌现）")
    s.add_argument("entity", help="实体名")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("view", help="视图层：把 data/ 的知识图谱渲染成单文件 HTML")
    s.add_argument("--out", default="", help="输出路径（默认 deliverables/graph.html）")
    s.add_argument("--json", action="store_true", help="只输出图谱 JSON（供桌面外壳调用）")

    s = sub.add_parser("pipeline", help="端到端：topic -> 关键词 -> 可信源 -> 拓扑 -> 图谱")
    s.add_argument("topic")
    s.add_argument("--dry-run", action="store_true", help="不写盘")

    s = sub.add_parser("draft", help="端到端预演（L1→L4）：返回将写入的实体/卡/边，不写盘（人工审核用）")
    s.add_argument("topic")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--top-k", type=int, default=5)
    s.add_argument("--min-score", type=float, default=graph.DEFAULT_MIN_SCORE)

    s = sub.add_parser("commit", help="把人工审核后的 draft 写盘（实体→wiki、卡→cards.md、边→edges.md）")
    s.add_argument("--file", dest="draft_file", required=True, help="draft JSON 文件路径")

    s = sub.add_parser("search", help="搜主题：可信源（平台）+ 条目（无可信源时提示去配置）")
    s.add_argument("topic")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--json", action="store_true", help="输出 JSON（界面用）")

    s = sub.add_parser("history", help="搜索历史（侧栏「搜索」下方用）")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("history-clear", help="清空搜索历史")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("modules", help="列出主题模块（含条目）")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("module-save", help="手工新建/更新一个搜索模块")
    s.add_argument("--topic", required=True)
    s.add_argument("--keywords", default="", help="逗号分隔；留空则自动拆词")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("module-delete", help="删除一个模块")
    s.add_argument("--id", dest="mid", required=True)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("platforms", help="列出可信源（平台）：内置 + 已收录")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("platform-add", help="手工补一个可信源（平台）")
    s.add_argument("--name", required=True)
    s.add_argument("--type", dest="stype", default="博客", help="规范|源码|书籍|论文|博客|社区")
    s.add_argument("--home", default="", help="平台入口 URL（决定归一 id，同站只算一个平台）")
    s.add_argument("--why", default="")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("platform-remove", help="删一个用户侧平台（内置平台删不掉）")
    s.add_argument("--id", dest="pid", required=True)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("entry-add", help="往主题模块加/覆盖一条条目（具体文件）")
    s.add_argument("--module", dest="mid", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--source", default="", help="所属平台 id（见 platforms）")
    s.add_argument("--locator", default="")
    s.add_argument("--note", default="")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("entry-remove", help="从主题模块删一条条目")
    s.add_argument("--module", dest="mid", required=True)
    s.add_argument("--title", required=True)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("llm-config", help="读模型资源配置（provider / 降级链 / MoA），明文 Key 不回传")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("llm-config-save", help="存模型资源配置（界面用；apiKey 留空 = 不改）")
    s.add_argument("--file", dest="config_file", required=True, help="配置 JSON 文件路径")

    s = sub.add_parser("llm-probe", help="逐个真调一次，报告谁能用（设置页的「测试」）")
    s.add_argument("--tier", default="all", help="main | cheap | all")

    return p


def _cmd_orient(args: argparse.Namespace) -> int:
    print(json.dumps({"topic": args.topic, "keywords": topic.orient(args.topic)}, ensure_ascii=False, indent=2))
    return 0


def _cmd_sources(args: argparse.Namespace) -> int:
    kws = topic.orient(args.topic)
    found = retrieve.find_sources(kws, limit=args.limit)
    payload: dict[str, Any] = {
        "topic": args.topic,
        "keywords": kws,
        "sources": [s.to_dict() for s in found],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_topology(args: argparse.Namespace) -> int:
    ns = topology.load_namespace(args.topic) if not args.topic else topology.build_namespace(args.topic, [])
    if args.json:
        print(
            json.dumps(
                {
                    "topic": ns.topic,
                    "entities": [{"name": e.name, "type": e.type, "one_line": e.one_line} for e in ns.entities],
                    "relations": [{"src": r.src, "dst": r.dst, "type": r.type} for r in ns.relations],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(f"namespace: {ns.topic}  实体 {len(ns.entities)}  关系 {len(ns.relations)}")
    for e in ns.entities:
        print(f"  · {e.name}（{e.type}）")
    for r in ns.relations:
        print(f"  {r.src} --{r.type}--> {r.dst}")
    return 0


def _cmd_attach(args: argparse.Namespace) -> int:
    ns = topology.load_namespace(args.topic)
    edges = graph.attach(ns, top_k=args.top_k, min_score=args.min_score, dry_run=args.dry_run)
    tag = "（dry-run，未写盘）" if args.dry_run else ""
    print(f"新增边 {len(edges)} 条{tag}")
    for e in edges:
        print(f"  {e.src} --{e.type}--> {e.dst}  [{e.confidence}] {e.reason}")
    return 0


def _cmd_profile(args: argparse.Namespace) -> int:
    if args.record:
        path = profile.record_event({"topic": args.topic, "action": args.action})
        print(f"已记录事件 -> {path}")
        return 0
    prof = profile.distill(profile.load_events())
    print(json.dumps(prof.preferences, ensure_ascii=False, indent=2))
    return 0


def _cmd_cards(args: argparse.Namespace) -> int:
    cards = mechanism.load_cards()
    if args.json:
        print(
            json.dumps(
                [
                    {"name": c.name, "problem": c.problem, "mechanism": c.mechanism,
                     "tradeoff": c.tradeoff, "boundary": c.boundary, "cases": c.cases}
                    for c in cards
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(f"机制卡 {len(cards)} 张")
    for c in cards:
        print(f"  · {c.name}  →  {'、'.join(c.cases) or '（无实例）'}")
    return 0


def _cmd_analogies(args: argparse.Namespace) -> int:
    hits = mechanism.analogies_of(args.entity)
    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print(f"「{args.entity}」未命中任何机制卡（无类比）")
        return 0
    for h in hits:
        print(f"  共享「{h['card']}」的同类：{'、'.join(h['siblings'])}")
    return 0


def _cmd_pipeline(args: argparse.Namespace) -> int:
    """端到端：五层串起来跑一遍（L5 不在此触发）。"""
    print(f"== L1 topic 定向：{args.topic}")
    kws = topic.orient(args.topic)
    print("   关键词:", "、".join(kws))
    print("== L2 检索层")
    srcs = retrieve.find_sources(kws)
    for s in srcs:
        print(f"   [{s.type}] {s.name}")
    print("== L3 拓扑层")
    ns = topology.build_namespace(args.topic, srcs)
    print(f"   实体 {len(ns.entities)}  关系 {len(ns.relations)}")
    print("== L4 图谱层")
    edges = graph.attach(ns, dry_run=args.dry_run)
    for e in edges[:10]:
        print(f"   {e.src} --{e.type}--> {e.dst}")
    print(f"   合计新增 {len(edges)} 条" + ("（dry-run，未写盘）" if args.dry_run else ""))
    return 0


def _relation_type(value: str) -> Literal["递进", "应用"]:
    return "应用" if value == "应用" else "递进"


def _platform_from_hit(hit: dict[str, Any]) -> Source:
    """搜索命中里的平台 dict → Source（非法 type 兜底成「博客」；id 缺失按 home 归一）。"""
    src = settings.parse_source(hit)
    if src is not None:
        return src
    return Source(name=str(hit.get("name", "")).strip(), type="博客", origin="builtin")


def _entry_from_hit(hit: dict[str, Any]) -> SourceEntry | None:
    """搜索命中里的条目 dict → SourceEntry（标题必填）。"""
    return settings.parse_entry(hit)


def _cmd_draft(args: argparse.Namespace) -> int:
    """L1→L4 预演（不写盘）：返回「将写入」的实体 / 机制卡 / 边，供界面人工审核。

    可信源复用搜索的解析结果（`allow_auto=False` + `record_history=False`，纯预演零副作用）：
    没有可信源时抽不出实体，返回空预览 + needsConfig，界面据此引导去配置。
    """
    result = retrieve.search_topic(
        args.topic, limit=args.limit, allow_auto=False, record_history=False
    )
    topic_text = str(result["topic"])
    keywords = [str(k) for k in result["keywords"]]
    source_hits = list(result["sources"])
    item_hits = list(result["items"])
    srcs = [_platform_from_hit(h) for h in source_hits]

    if not srcs:
        return _print_draft(
            {
                "topic": topic_text,
                "keywords": keywords,
                "sources": source_hits,
                "items": item_hits,
                "matched": False,
                "needsConfig": True,
                "llmError": llm.last_llm_error(),
                "llmRoute": llm.last_llm_route(),
                "llmDegraded": llm.last_llm_degraded(),
                "entities": [],
                "relations": [],
                "cards": [],
                "edges": [],
            }
        )

    ns = topology.build_namespace(topic_text, srcs)
    cards, edges = graph.plan(ns, top_k=args.top_k, min_score=args.min_score)
    return _print_draft(
        {
            "topic": topic_text,
            "keywords": keywords,
            "sources": source_hits,
            "items": item_hits,
            "matched": True,
            "needsConfig": False,
            # 抽不出实体时，界面靠它区分「模型调用失败」与「模型没给」
            "llmError": llm.last_llm_error(),
            # 降级必须可见：谁服务的、有没有降级
            "llmRoute": llm.last_llm_route(),
            "llmDegraded": llm.last_llm_degraded(),
            "entities": [{"name": e.name, "type": e.type, "oneLine": e.one_line} for e in ns.entities],
            "relations": [{"src": r.src, "dst": r.dst, "type": r.type} for r in ns.relations],
            "cards": [
                {
                    "name": c.name,
                    "problem": c.problem,
                    "mechanism": c.mechanism,
                    "tradeoff": c.tradeoff,
                    "boundary": c.boundary,
                    "cases": c.cases,
                }
                for c in cards
            ],
            "edges": [
                {"src": e.src, "dst": e.dst, "type": e.type, "confidence": e.confidence, "reason": e.reason}
                for e in edges
            ],
        }
    )


def _print_draft(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _apply_draft(raw: dict[str, Any], *, notes_dir: Path | None = None) -> dict[str, Any]:
    """按人工审核后的 draft 落盘（幂等）：实体→wiki 卡、机制卡→cards.md、边→edges.md。"""
    topic_text = str(raw.get("topic", "")).strip()
    sources = [_platform_from_hit(h) for h in (raw.get("sources") or []) if isinstance(h, dict)]
    entities = [
        Entity(
            name=str(e.get("name", "")).strip(),
            type=str(e.get("type", "概念")).strip() or "概念",
            one_line=str(e.get("oneLine", e.get("one_line", ""))).strip(),
        )
        for e in (raw.get("entities") or [])
        if isinstance(e, dict) and str(e.get("name", "")).strip()
    ]
    relations = [
        Relation(
            src=str(r.get("src", "")).strip(),
            dst=str(r.get("dst", "")).strip(),
            type=_relation_type(str(r.get("type", "递进"))),
        )
        for r in (raw.get("relations") or [])
        if isinstance(r, dict) and str(r.get("src", "")).strip() and str(r.get("dst", "")).strip()
    ]
    cards = [
        MechanismCard(
            name=str(c.get("name", "")).strip(),
            problem=str(c.get("problem", "")).strip(),
            mechanism=str(c.get("mechanism", "")).strip(),
            tradeoff=str(c.get("tradeoff", "")).strip(),
            boundary=str(c.get("boundary", "")).strip(),
            cases=[str(x).strip() for x in (c.get("cases") or []) if str(x).strip()],
        )
        for c in (raw.get("cards") or [])
        if isinstance(c, dict) and str(c.get("name", "")).strip()
    ]
    edges = [
        Edge(
            src=str(e.get("src", "")).strip(),
            dst=str(e.get("dst", "")).strip(),
            type=_relation_type(str(e.get("type", "递进"))),
            confidence=str(e.get("confidence", "high")).strip() or "high",
            reason=str(e.get("reason", "")).strip(),
        )
        for e in (raw.get("edges") or [])
        if isinstance(e, dict) and str(e.get("src", "")).strip() and str(e.get("dst", "")).strip()
    ]

    ns = Namespace(topic=topic_text, sources=sources, entities=entities, relations=relations)
    written = topology.write_entity_cards(ns, entities, notes_dir=notes_dir)
    if cards:
        mechanism.upsert_cards(cards)
    if edges:
        graph.write_edges(edges)
    return {"writtenEntities": written, "cards": len(cards), "edges": len(edges)}


def _cmd_commit(args: argparse.Namespace) -> int:
    draft_path = Path(args.draft_file)
    raw = json.loads(draft_path.read_text(encoding="utf-8"))
    print(json.dumps(_apply_draft(raw), ensure_ascii=False))
    return 0


def _cmd_view(args: argparse.Namespace) -> int:
    from pathlib import Path

    if args.json:
        # 外壳（Electron 等）走这条：只吐 JSON，不写盘
        print(json.dumps(view.build_graph_data(), ensure_ascii=False))
        return 0

    out = view.write_html(Path(args.out)) if args.out else view.write_html()
    data = view.build_graph_data()
    print(f"已生成 {out}")
    print(f"  实体 {len(data['nodes'])} · 边 {len(data['links'])}")
    if data["dangling"]:
        print(f"  端点未建卡的边 {len(data['dangling'])} 条（跨域节点，允许）")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    """搜主题：L1 关键词 + L2 可信源（平台）与条目；无可信源时带 needsConfig 供界面提示。

    注意：**无匹配也退出 0**（那是正常结果，由 JSON 的 matched/needsConfig 表达）；
    非 0 只留给真错误，避免外壳把「没找到」误判成「调用失败」。
    """
    result = retrieve.search_topic(args.topic, limit=args.limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print(f"主题：{result['topic']}")
    print("关键词：" + "、".join(result["keywords"]))
    if not result["matched"]:
        print("⚠ 未找到匹配的可信源 —— 去「设置」里配置可信搜索源")
        return 0
    print(f"可信源 {len(result['sources'])} 个平台 · 条目 {len(result['items'])} 条")
    for s in result["sources"]:
        print(f"  [{s['type']}] {s['name']}  ({s['origin']})  {s['home']}")
    for it in result["items"]:
        print(f"    · {it['title']}  → {it['locator'] or it['source']}")
    return 0


def _module_payload(mods: list[settings.TrustedModule]) -> list[dict[str, Any]]:
    return [m.to_dict() for m in mods]


def _modules_json(mods: list[settings.TrustedModule]) -> None:
    print(json.dumps({"modules": _module_payload(mods)}, ensure_ascii=False))


def _platforms_json(platforms: list[Source]) -> None:
    print(json.dumps({"platforms": [p.to_dict() for p in platforms]}, ensure_ascii=False))


def _history_payload(history: list[settings.HistoryItem]) -> list[dict[str, Any]]:
    return [h.to_dict() for h in history]


def _history_json(history: list[settings.HistoryItem]) -> None:
    print(json.dumps({"history": _history_payload(history)}, ensure_ascii=False))


def _cmd_history(args: argparse.Namespace) -> int:
    history = settings.load_history()
    if args.json:
        _history_json(history)
        return 0
    if not history:
        print("（还没有搜索历史）")
        return 0
    for h in history:
        mark = f"{h.source_count} 个平台" if h.matched else "未命中"
        print(f"  {h.at}  {h.topic}  （{mark}）")
    return 0


def _cmd_history_clear(args: argparse.Namespace) -> int:
    history = settings.clear_history()
    if args.json:
        _history_json(history)
        return 0
    print("已清空搜索历史")
    return 0


def _cmd_modules(args: argparse.Namespace) -> int:
    mods = settings.load_modules()
    if args.json:
        _modules_json(mods)
        return 0
    if not mods:
        print("（还没有主题模块）")
        return 0
    for m in mods:
        tag = "AI自动" if m.origin == "auto" else "手工"
        print(f"  [{tag}] {m.topic}  ({len(m.items)} 条条目 / {len(m.platform_ids())} 个平台)")
    return 0


def _cmd_module_save(args: argparse.Namespace) -> int:
    from app.layers.topic import orient as orient_topic

    topic_text = args.topic.strip()
    if not topic_text:
        print("❌ 主题不能为空", file=sys.stderr)
        return 2
    keywords = [k.strip() for k in str(args.keywords).split(",") if k.strip()]
    if not keywords:
        keywords = orient_topic(topic_text)
    mid = settings.module_id(topic_text)
    existing = {m.id: m for m in settings.load_modules()}.get(mid)
    module = settings.TrustedModule(
        id=mid,
        topic=topic_text,
        origin="manual",
        keywords=keywords,
        items=list(existing.items) if existing else [],
        created_at=existing.created_at if existing else "",
    )
    mods = settings.upsert_module(module)
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已保存模块「{topic_text}」（{len(module.items)} 条条目）")
    return 0


def _cmd_module_delete(args: argparse.Namespace) -> int:
    mods = settings.delete_module(args.mid)
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已删除模块 {args.mid}，剩余 {len(mods)} 个")
    return 0


def _valid_type(stype: str) -> str | None:
    """校验来源类型（非法时返回 None）。"""
    value = stype.strip()
    return value if value in settings.VALID_TYPES else None


def _cmd_platforms(args: argparse.Namespace) -> int:
    platforms = settings.load_platforms()
    if args.json:
        _platforms_json(platforms)
        return 0
    for p in platforms:
        print(f"  [{p.type}] {p.name}  ({p.id})  {p.home}")
    return 0


def _cmd_platform_add(args: argparse.Namespace) -> int:
    stype = _valid_type(str(args.stype))
    if stype is None:
        print(f"❌ 未知来源类型：{args.stype}（可选：{'|'.join(settings.VALID_TYPES)}）", file=sys.stderr)
        return 2
    name = args.name.strip()
    if not name:
        print("❌ 平台名不能为空", file=sys.stderr)
        return 2
    # 上方已按 settings.VALID_TYPES 校验，mypy 收窄不了 str→Literal
    platform = Source(
        name=name,
        type=stype,  # type: ignore[arg-type]
        why=args.why,
        home=args.home.strip(),
        id=settings.platform_id(name, args.home),
        origin="manual",
    )
    platforms = settings.register_platforms([platform])
    saved = next((p for p in platforms if p.id == platform.id), platform)
    if args.json:
        # 回报**归一后的那条**：同名同站会归入已有平台（id 相同），界面据此说实话
        # （否则用户输入「GitHub 副本」，界面却找不到这个名字）
        print(
            json.dumps(
                {"platform": saved.to_dict(), "platforms": [p.to_dict() for p in platforms]},
                ensure_ascii=False,
            )
        )
        return 0
    print(f"已保存可信源「{saved.name}」（{saved.id}）")
    return 0


def _cmd_platform_remove(args: argparse.Namespace) -> int:
    platforms = settings.remove_platform(args.pid.strip())
    if args.json:
        _platforms_json(platforms)
        return 0
    print(f"已删除可信源 {args.pid}（剩余 {len(platforms)} 个）")
    return 0


def _cmd_entry_add(args: argparse.Namespace) -> int:
    title = args.title.strip()
    if not title:
        print("❌ 条目标题不能为空", file=sys.stderr)
        return 2
    entry = SourceEntry(
        title=title, source=args.source.strip(), locator=args.locator.strip(), note=args.note.strip()
    )
    try:
        mods = settings.add_module_item(args.mid, entry)
    except KeyError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已保存条目「{entry.title}」到模块 {args.mid}")
    return 0


def _cmd_entry_remove(args: argparse.Namespace) -> int:
    try:
        mods = settings.remove_module_item(args.mid, args.title.strip())
    except KeyError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已从模块 {args.mid} 删除条目「{args.title}」")
    return 0


def _cmd_llm_config(args: argparse.Namespace) -> int:
    print(json.dumps(settings.llm_config_payload(), ensure_ascii=False, indent=2))
    return 0


def _cmd_llm_config_save(args: argparse.Namespace) -> int:
    raw = json.loads(Path(args.config_file).read_text(encoding="utf-8"))
    print(json.dumps(settings.save_llm_config_payload(raw), ensure_ascii=False))
    return 0


def _cmd_llm_probe(args: argparse.Namespace) -> int:
    tiers = ["main", "cheap"] if args.tier == "all" else [args.tier]
    payload = {"tiers": [{"tier": t, "results": llm.probe(t)} for t in tiers]}
    print(json.dumps(payload, ensure_ascii=False))
    return 0


_DISPATCH = {
    "orient": _cmd_orient,
    "sources": _cmd_sources,
    "topology": _cmd_topology,
    "attach": _cmd_attach,
    "profile": _cmd_profile,
    "cards": _cmd_cards,
    "analogies": _cmd_analogies,
    "view": _cmd_view,
    "pipeline": _cmd_pipeline,
    "draft": _cmd_draft,
    "commit": _cmd_commit,
    "search": _cmd_search,
    "history": _cmd_history,
    "history-clear": _cmd_history_clear,
    "modules": _cmd_modules,
    "module-save": _cmd_module_save,
    "module-delete": _cmd_module_delete,
    "platforms": _cmd_platforms,
    "platform-add": _cmd_platform_add,
    "platform-remove": _cmd_platform_remove,
    "entry-add": _cmd_entry_add,
    "entry-remove": _cmd_entry_remove,
    "llm-config": _cmd_llm_config,
    "llm-config-save": _cmd_llm_config_save,
    "llm-probe": _cmd_llm_probe,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0
    return _DISPATCH[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
