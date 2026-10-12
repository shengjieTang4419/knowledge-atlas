"""薄入口：只做参数解析与分层调用，不写业务（业务在 layers/）。"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app import settings, view
from app.layers import graph, mechanism, profile, retrieve, topic, topology
from app.models import Source


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

    s = sub.add_parser("search", help="搜主题：关键词 + 可信源（无可信源时提示去配置）")
    s.add_argument("topic")
    s.add_argument("--limit", type=int, default=5)
    s.add_argument("--json", action="store_true", help="输出 JSON（界面用）")

    s = sub.add_parser("modules", help="列出可信源模块（按 topic 分组）")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("module-save", help="手工新建/更新一个搜索模块")
    s.add_argument("--topic", required=True)
    s.add_argument("--keywords", default="", help="逗号分隔；留空则自动拆词")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("module-delete", help="删除一个模块")
    s.add_argument("--id", dest="mid", required=True)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("source-add", help="往模块里加/覆盖一条可信源")
    s.add_argument("--module", dest="mid", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--type", dest="stype", default="博客", help="规范|源码|书籍|论文|博客|社区")
    s.add_argument("--locator", default="")
    s.add_argument("--why", default="")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("source-remove", help="从模块里删一条可信源")
    s.add_argument("--module", dest="mid", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--json", action="store_true")

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
        "sources": [{"name": s.name, "type": s.type, "why": s.why, "locator": s.locator} for s in found],
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
    """搜主题：L1 关键词 + L2 可信源；无可信源时带 needsConfig 供界面提示。

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
    for s in result["sources"]:
        print(f"  [{s['type']}] {s['name']}  ({s['origin']})")
    return 0


def _module_payload(mods: list[settings.TrustedModule]) -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "topic": m.topic,
            "origin": m.origin,
            "keywords": m.keywords,
            "createdAt": m.created_at,
            "updatedAt": m.updated_at,
            "sources": [
                {"name": x.name, "type": x.type, "why": x.why, "locator": x.locator} for x in m.sources
            ],
        }
        for m in mods
    ]


def _modules_json(mods: list[settings.TrustedModule]) -> None:
    print(json.dumps({"modules": _module_payload(mods)}, ensure_ascii=False))


def _cmd_modules(args: argparse.Namespace) -> int:
    mods = settings.load_modules()
    if args.json:
        _modules_json(mods)
        return 0
    if not mods:
        print("（还没有可信源模块）")
        return 0
    for m in mods:
        tag = "AI自动" if m.origin == "auto" else "手工"
        print(f"  [{tag}] {m.topic}  ({len(m.sources)} 条源)")
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
        sources=list(existing.sources) if existing else [],
        created_at=existing.created_at if existing else "",
    )
    mods = settings.upsert_module(module)
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已保存模块「{topic_text}」（{len(module.sources)} 条源）")
    return 0


def _cmd_module_delete(args: argparse.Namespace) -> int:
    mods = settings.delete_module(args.mid)
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已删除模块 {args.mid}，剩余 {len(mods)} 个")
    return 0


def _cmd_source_add(args: argparse.Namespace) -> int:
    stype = str(args.stype).strip()
    if stype not in settings.VALID_TYPES:
        print(f"❌ 未知来源类型：{stype}（可选：{'|'.join(settings.VALID_TYPES)}）", file=sys.stderr)
        return 2
    source = Source(name=args.name.strip(), type=stype, why=args.why, locator=args.locator)  # type: ignore[arg-type]
    try:
        mods = settings.add_module_source(args.mid, source)
    except KeyError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已保存「{source.name}」到模块 {args.mid}")
    return 0


def _cmd_source_remove(args: argparse.Namespace) -> int:
    try:
        mods = settings.remove_module_source(args.mid, args.name.strip())
    except KeyError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    if args.json:
        _modules_json(mods)
        return 0
    print(f"已从模块 {args.mid} 删除「{args.name}」")
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
    "search": _cmd_search,
    "modules": _cmd_modules,
    "module-save": _cmd_module_save,
    "module-delete": _cmd_module_delete,
    "source-add": _cmd_source_add,
    "source-remove": _cmd_source_remove,
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
