"""可信源「两层 + 历史」验收。

核心口径：
1. **可信源 = 平台级**（泛化、跨主题复用，id 取宿主域名）；**条目 = 文件级**，挂在主题模块下；
2. 搜主题时 AI 判定 → 自动收录（平台进全局注册表、条目进模块），下次同 topic 直接命中；
3. 搜索历史持久化（侧栏「搜索」下方展示）：同主题只一条、上限封顶、预演不写。
"""
import json

import pytest

from app import llm, settings
from app.layers import retrieve
from app.models import Source, SourceEntry


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    """只隔离设置目录（不污染真实 data/settings）。

    网络隔离由 tests/conftest.py 的全局 fixture 负责（清 LLM 环境变量）。
    """
    monkeypatch.setattr(settings, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "settings.json")
    yield


def _online_without_network(
    monkeypatch,
    platforms: list[Source] | None = None,
    entries: list[SourceEntry] | None = None,
) -> None:
    """打开「在线」分支，但**绝不发真实请求**。

    ⚠ 必须 mock 到**源头** `app.llm.chat_json`，不能只 patch `retrieve.chat_json`：
    `topic.py` 是 `from app.llm import chat_json` 的**独立绑定**，patch 别处拦不住它，
    于是 `orient()` 会真调一次模型拆词。实测代价：每个用例慢 1.5~6.5s、
    且结果依赖模型输出（同一份代码时绿时红）。

    - `llm.chat_json`        → 覆盖所有 `from app.llm import chat_json` 的模块
    - `retrieve._llm_sources` → 直接给出判定结果（跳过 AI 环节）
    """
    monkeypatch.setattr(llm, "_FORCE_OFFLINE", False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {})
    monkeypatch.setattr(
        retrieve,
        "_llm_sources",
        lambda topic, keywords: (list(platforms or []), list(entries or [])),
    )


def _add_entry(mid: str, title: str, source: str = "", locator: str = "", **kw: str) -> list[settings.TrustedModule]:
    return settings.add_module_item(
        mid, SourceEntry(title=title, source=source, locator=locator, **kw)
    )


def _new_module(topic: str, origin: str = "manual", keywords: list[str] | None = None) -> settings.TrustedModule:
    return settings.TrustedModule(
        id=settings.module_id(topic), topic=topic, origin=origin, keywords=keywords or [topic]
    )


def _arxiv(why: str = "") -> Source:
    return Source(
        name="arXiv", type="论文", why=why, home="https://arxiv.org", id="arxiv.org", origin="auto"
    )


# ---------- 模块数据结构 ----------


def test_module_id_is_stable_and_whitespace_insensitive():
    assert settings.module_id("Java 多线程") == settings.module_id("Java多线程")
    assert settings.module_id("   ") == ""


def test_empty_settings_has_no_modules():
    assert settings.load_modules() == []


def test_upsert_module_creates_then_updates():
    settings.upsert_module(_new_module("Rust 所有权"))
    assert len(settings.load_modules()) == 1
    # 同 topic 再存 = 更新，不新增
    settings.upsert_module(_new_module("Rust 所有权"))
    assert len(settings.load_modules()) == 1


def test_upsert_preserves_created_at():
    mods = settings.upsert_module(_new_module("A"))
    first_created = mods[0].created_at
    mods = settings.upsert_module(_new_module("A"))
    assert mods[0].created_at == first_created
    assert mods[0].updated_at >= first_created


def test_origin_auto_vs_manual_recorded():
    settings.upsert_module(_new_module("AI 生成的主题", origin="auto"))
    settings.upsert_module(_new_module("我手工建的主题", origin="manual"))
    by_topic = {m.topic: m.origin for m in settings.load_modules()}
    assert by_topic["AI 生成的主题"] == "auto"
    assert by_topic["我手工建的主题"] == "manual"


def test_add_and_remove_entry_in_module():
    mid = settings.upsert_module(_new_module("Rust"))[0].id
    _add_entry(mid, "Rust 官方文档", "doc.rust-lang.org", "https://doc.rust-lang.org/")
    assert [e.title for e in settings.load_modules()[0].items] == ["Rust 官方文档"]
    # 同标题覆盖
    _add_entry(mid, "Rust 官方文档", "doc.rust-lang.org", "https://doc.rust-lang.org/book/")
    mods = settings.load_modules()
    assert len(mods[0].items) == 1
    assert mods[0].items[0].locator == "https://doc.rust-lang.org/book/"
    # 删除
    settings.remove_module_item(mid, "Rust 官方文档")
    assert settings.load_modules()[0].items == []


def test_manual_edit_flips_origin_to_manual():
    """AI 生成的模块被我手工改过之后，就标成 manual（不该再被当纯自动）。"""
    mid = settings.upsert_module(_new_module("AI 主题", origin="auto"))[0].id
    _add_entry(mid, "我补的条目", "example.com")
    assert settings.load_modules()[0].origin == "manual"


def test_add_entry_to_missing_module_raises():
    with pytest.raises(KeyError):
        _add_entry("不存在的模块", "x")


def test_delete_module():
    settings.upsert_module(_new_module("A"))
    settings.upsert_module(_new_module("B"))
    left = settings.delete_module(settings.module_id("A"))
    assert [m.topic for m in left] == ["B"]
    assert settings.delete_module("不存在") is not None  # 幂等，不抛


def test_match_modules_by_topic_keyword_entry_title():
    mid = settings.upsert_module(_new_module("Rust 所有权"))[0].id
    _add_entry(mid, "Rust 官方文档", "doc.rust-lang.org")
    assert [m.topic for m in settings.match_modules(["Rust"])] == ["Rust 所有权"]
    assert [m.topic for m in settings.match_modules(["所有权"])] == ["Rust 所有权"]
    assert settings.match_modules(["园艺", "种花"]) == []


def test_ascii_keyword_matches_whole_word_not_substring():
    """实测踩坑：搜 `transform` 命中「Sentence Transformers」、`ai` 命中 `FAISS`——
    子串匹配把不相关的源当成「可信源找到了」端给用户。"""
    mid = settings.upsert_module(_new_module("RAG 检索"))[0].id
    _add_entry(mid, "Sentence Transformers 官方文档", "sbert.net")
    _add_entry(mid, "FAISS 向量库", "faiss.ai")
    assert settings.match_modules(["transform"]) == [], "transform 不该命中 Transformers"
    assert settings.match_modules(["ai"]) == [], "ai 不该命中 FAISS"
    # 整词仍要命中，别改严了漏掉
    assert [m.topic for m in settings.match_modules(["transformers"])] == ["RAG 检索"]


def test_ascii_matching_is_strict_no_plural_folding():
    """不做单复数容错：`transformer` vs `Transformers` 也是两个意思。

    宁可漏掉缓存（回落 AI 判定，多花一次 token），也不给错源。
    """
    mid = settings.upsert_module(_new_module("向量表示"))[0].id
    _add_entry(mid, "Embeddings 官方文档", "sbert.net")
    assert settings.match_modules(["embedding"]) == [], "单数不该命中复数"
    assert settings.match_modules(["transform"]) == [], "transform 不该命中 Transformers"
    # 原词照常命中
    assert settings.match_modules(["embeddings"]) != []


def test_chinese_keyword_still_matches_by_substring():
    """中文没有词边界，子串才是有意义的包含。"""
    mid = settings.upsert_module(_new_module("RAG 检索"))[0].id
    _add_entry(mid, "向量数据库与相似度检索", "zhihu.com")
    assert [m.topic for m in settings.match_modules(["向量数据库"])] == ["RAG 检索"]


def test_corrupt_settings_file_is_tolerated():
    settings.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text("{坏 json", encoding="utf-8")
    assert settings.load_modules() == []


# ---------- 旧格式迁移 ----------


def test_legacy_flat_format_is_migrated():
    """旧格式（扁平 trusted_sources）不丢数据：迁成一个手工模块。"""
    settings.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text(
        json.dumps(
            {
                "trusted_sources": [
                    {"name": "老源", "type": "规范", "why": "权威", "locator": "https://jcp.org/en/jsr"}
                ]
            }
        ),
        encoding="utf-8",
    )
    mods = settings.load_modules()
    assert len(mods) == 1
    assert mods[0].origin == "manual"
    assert [e.title for e in mods[0].items] == ["老源"]


def test_legacy_module_sources_split_into_platform_and_entries():
    """拆两层前的模块（sources = 平台与文件混体）→ 条目 + 平台，且同站自动收敛。"""
    settings.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text(
        json.dumps(
            {
                "modules": [
                    {
                        "id": "rag",
                        "topic": "RAG",
                        "origin": "auto",
                        "keywords": ["RAG"],
                        "sources": [
                            {"name": "RAG 论文", "type": "论文", "why": "奠基", "locator": "https://arxiv.org/abs/2005.11401"},
                            {"name": "RAGAS", "type": "论文", "why": "评估", "locator": "https://arxiv.org/abs/2309.15217"},
                            {"name": "Faiss", "type": "源码", "why": "索引", "locator": "https://github.com/facebookresearch/faiss"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    items = settings.load_modules()[0].items
    assert [e.title for e in items] == ["RAG 论文", "RAGAS", "Faiss"]
    # 两条 arXiv 收敛成一个平台（这正是拆两层要的结果：平台数由「站」决定）
    assert [e.source for e in items] == ["arxiv.org", "arxiv.org", "github.com"]
    assert {p.id for p in settings.load_user_platforms()} == {"arxiv.org", "github.com"}
    assert next(p for p in settings.load_user_platforms() if p.id == "arxiv.org").name == "arxiv.org"


def test_migration_keeps_history_and_other_sections(tmp_path):
    """写一段不能抹掉另外两段：迁移与写盘都保住 `history` / `platforms`。"""
    settings.record_search("主题甲", True, 2)
    settings.upsert_module(_new_module("主题甲"))
    raw = json.loads(settings.SETTINGS_PATH.read_text(encoding="utf-8"))
    assert [h["topic"] for h in raw["history"]] == ["主题甲"]
    assert "platforms" in raw and "modules" in raw


# ---------- 可信源（平台）注册表 ----------


def test_builtin_platforms_are_loaded_from_config():
    ids = {p.id for p in settings.load_platforms()}
    assert {"jcp.org", "github.com", "oreilly.com", "gee.cs.oswego.edu"} <= ids


def test_register_platforms_skips_known_ids_and_builtin_wins():
    settings.register_platforms([Source(name="GitHub 副本", type="博客", home="https://github.com")])
    named = {p.id: p.name for p in settings.load_platforms()}
    assert named["github.com"] == "GitHub", "内置平台先到先得，不该被用户侧覆盖"
    assert not settings.load_user_platforms() or all(
        p.id != "github.com" for p in settings.load_user_platforms()
    )


def test_register_then_remove_platform():
    settings.register_platforms([Source(name="知乎", type="社区", home="https://zhihu.com")])
    assert "zhihu.com" in {p.id for p in settings.load_user_platforms()}
    settings.remove_platform("zhihu.com")
    assert "zhihu.com" not in {p.id for p in settings.load_user_platforms()}


def test_builtin_platform_cannot_be_removed():
    settings.remove_platform("github.com")
    assert "github.com" in {p.id for p in settings.load_platforms()}


# ---------- 平台归一（防「零散可信源」）----------


def test_normalize_platforms_merges_same_host():
    platforms = [
        _arxiv("奠基"),
        _arxiv("评估"),
        Source(name="GitHub", type="源码", home="https://github.com", id="github.com"),
    ]
    entries = [
        SourceEntry(title="论文 A", source="arXiv", locator="https://arxiv.org/abs/1"),
        SourceEntry(title="论文 B", source="arXiv", locator="https://arxiv.org/abs/2"),
        SourceEntry(title="实现", source="GitHub", locator="https://github.com/x/y"),
    ]
    got, out = retrieve.normalize_platforms(platforms, entries)
    assert [p.id for p in got] == ["arxiv.org", "github.com"]
    assert [e.source for e in out] == ["arxiv.org", "arxiv.org", "github.com"]


def test_normalize_recreates_missing_platform_from_locator_host():
    """模型漏给平台：按条目域名兜底补一个（可改），而不是丢条目。"""
    got, out = retrieve.normalize_platforms([], [SourceEntry(title="X", locator="https://example.com/a")])
    assert [p.id for p in got] == ["example.com"]
    assert out[0].source == "example.com"
    assert got[0].type == "博客", "类型不明取最低档，不冒充高可信"


def test_normalize_drops_entry_without_platform_or_locator():
    got, out = retrieve.normalize_platforms([], [SourceEntry(title="没头没主")])
    assert got == [] and out == []


def test_normalize_drops_unreferenced_platform():
    got, _out = retrieve.normalize_platforms([_arxiv()], [])
    assert got == [], "没有条目支撑的平台是噪声"


# ---------- 搜索编排 ----------


def test_search_hits_builtin_first():
    r = retrieve.search_topic("Java 多线程 · 内存可见性")
    assert r["matched"] is True
    assert {s["origin"] for s in r["sources"]} == {"builtin"}
    assert r["autoCollected"] is False
    # 内置模块现在是「平台 + 条目」两层
    assert len(r["sources"]) == 4
    assert len(r["items"]) == 4
    assert {i["source"] for i in r["items"]} == {s["id"] for s in r["sources"]}


def test_search_hits_user_module():
    mid = settings.upsert_module(_new_module("Rust 所有权"))[0].id
    settings.register_platforms([Source(name="Rust 官方文档", type="规范", home="https://doc.rust-lang.org")])
    _add_entry(mid, "Rust 官方文档", "doc.rust-lang.org", "https://doc.rust-lang.org/")
    r = retrieve.search_topic("Rust 所有权")
    assert r["matched"] is True
    assert r["sources"][0]["origin"] == "manual"
    assert r["moduleId"] == mid
    assert r["items"][0]["title"] == "Rust 官方文档"


def test_user_module_entry_with_dangling_platform_still_hits():
    """注册表里没有这个平台（如被删过）时，按条目域名兜底，不让整次搜索白跑。"""
    mid = settings.upsert_module(_new_module("Rust 所有权"))[0].id
    _add_entry(mid, "Rust 官方文档", "doc.rust-lang.org", "https://doc.rust-lang.org/")
    r = retrieve.search_topic("Rust 所有权")
    assert r["matched"] is True
    assert r["sources"][0]["id"] == "doc.rust-lang.org"


def test_search_no_match_reports_needs_config():
    r = retrieve.search_topic("园艺种花")
    assert r["matched"] is False
    assert r["needsConfig"] is True
    assert r["moduleCount"] == 0
    assert r["items"] == []


def test_search_auto_collects_module_with_llm(monkeypatch):
    """AI 判定 → 自动收录：平台进注册表、条目进模块（核心诉求）。"""
    _online_without_network(
        monkeypatch,
        [
            Source(name="Rust 官方文档", type="规范", home="https://doc.rust-lang.org"),
            Source(name="GitHub", type="源码", home="https://github.com"),
        ],
        [
            SourceEntry(title="Rust Reference", source="Rust 官方文档", locator="https://doc.rust-lang.org/reference/"),
            SourceEntry(title="rust-lang/rust 源码", source="GitHub", locator="https://github.com/rust-lang/rust"),
        ],
    )
    r = retrieve.search_topic("Rust 所有权")
    assert r["matched"] is True
    assert r["autoCollected"] is True
    assert {s["origin"] for s in r["sources"]} == {"auto"}
    assert {s["id"] for s in r["sources"]} == {"doc.rust-lang.org", "github.com"}
    assert [i["title"] for i in r["items"]] == ["Rust Reference", "rust-lang/rust 源码"]

    # 已落盘：模块标 auto，平台进了注册表
    mods = settings.load_modules()
    assert len(mods) == 1
    assert mods[0].origin == "auto"
    assert [e.title for e in mods[0].items][0] == "Rust Reference", "规范应排最前"
    assert "doc.rust-lang.org" in {p.id for p in settings.load_platforms()}


def test_auto_collect_collapses_same_platform(monkeypatch):
    """模型列了 3 篇 arXiv 论文 → 只有 1 个可信源（arXiv）+ 3 条条目，而不是 3 条散装可信源。"""
    _online_without_network(
        monkeypatch,
        [_arxiv("a"), _arxiv("b"), _arxiv("c")],
        [
            SourceEntry(title="论文 A", source="arXiv", locator="https://arxiv.org/abs/1"),
            SourceEntry(title="论文 B", source="arXiv", locator="https://arxiv.org/abs/2"),
            SourceEntry(title="论文 C", source="arXiv", locator="https://arxiv.org/abs/3"),
        ],
    )
    r = retrieve.search_topic("RAG 评估")
    assert len(r["sources"]) == 1
    assert r["sources"][0]["id"] == "arxiv.org"
    assert len(r["items"]) == 3


def test_second_search_hits_collected_module_without_llm(monkeypatch):
    """第二次搜同主题：直接命中已收录模块，**连 L1 拆词都不再调模型**（落盘即缓存）。"""
    from app.layers import topic as topic_mod

    _online_without_network(
        monkeypatch,
        [Source(name="Rust 官方文档", type="规范", home="https://doc.rust-lang.org")],
        [SourceEntry(title="Rust 官方文档", source="Rust 官方文档", locator="https://doc.rust-lang.org/")],
    )
    calls = {"n": 0, "orient": 0}
    real = retrieve._llm_sources
    real_orient = topic_mod.orient

    def counting(topic: str, keywords: list[str]) -> tuple[list[Source], list[SourceEntry]]:
        calls["n"] += 1
        return real(topic, keywords)

    def counting_orient(t: str) -> list[str]:
        calls["orient"] += 1
        return real_orient(t)

    monkeypatch.setattr(retrieve, "_llm_sources", counting)
    monkeypatch.setattr(topic_mod, "orient", counting_orient)
    retrieve.search_topic("Rust 所有权")
    assert calls == {"n": 1, "orient": 1}

    # 第二次：即使 LLM 不可用，也应命中模块，且一次模型都不调
    monkeypatch.setattr(llm, "_FORCE_OFFLINE", True)
    r = retrieve.search_topic("Rust 所有权")
    assert r["matched"] is True
    assert r["autoCollected"] is False, "第二次是缓存命中，不是新收录"
    assert r["keywords"], "关键词来自模块里存的那份，不该为空"
    assert calls == {"n": 1, "orient": 1}, "缓存命中不该再调模型"


def test_auto_collect_skips_save_when_llm_returns_nothing(monkeypatch):
    """模型没给出「平台 + 条目」→ 不落盘（不污染设置）。"""
    _online_without_network(monkeypatch)
    r = retrieve.search_topic("冷门主题")
    assert r["matched"] is False
    assert r["needsConfig"] is True
    assert settings.load_modules() == []
    assert settings.load_user_platforms() == []


def test_auto_collect_requires_entries(monkeypatch):
    """只给平台、给不出条目 → 视为没找到（可信源必须由条目支撑）。"""
    _online_without_network(monkeypatch, [Source(name="arXiv", type="论文", home="https://arxiv.org")])
    r = retrieve.search_topic("冷门主题")
    assert r["matched"] is False
    assert settings.load_modules() == []


def test_allow_auto_false_never_calls_llm(monkeypatch):
    _online_without_network(
        monkeypatch,
        [Source(name="Rust 官方文档", type="规范", home="https://doc.rust-lang.org")],
        [SourceEntry(title="Rust 官方文档", locator="https://doc.rust-lang.org/")],
    )

    def boom(topic: str, keywords: list[str]) -> tuple[list[Source], list[SourceEntry]]:
        raise AssertionError("不该调模型")

    monkeypatch.setattr(retrieve, "_llm_sources", boom)
    r = retrieve.search_topic("冷门主题", allow_auto=False)
    assert r["matched"] is False


def test_search_reports_llm_availability(monkeypatch):
    """llmAvailable 反映「是否配了模型」，界面据此解释「为什么没自动生成」。

    注意：本测试环境**禁网**（见 conftest），但 `is_online()` 只看配置不看连通性，
    所以这里显式两种都断言，避免依赖本机 .env 的偶然状态。
    """
    # 配了 key → True（即使网络被禁，配置层面是"可用"）
    monkeypatch.setattr(llm, "_FORCE_OFFLINE", False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert retrieve.search_topic("园艺种花")["llmAvailable"] is True

    # 没配 → False
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(llm, "_FORCE_OFFLINE", True)
    assert retrieve.search_topic("园艺种花")["llmAvailable"] is False


def test_search_empty_topic():
    r = retrieve.search_topic("  ")
    assert r["topic"] == ""
    assert r["matched"] is False
    assert r["needsConfig"] is False, "空输入不该提示去配置"


# ---------- 搜索历史 ----------


def test_search_records_history():
    retrieve.search_topic("Java 多线程 · 内存可见性")
    history = settings.load_history()
    assert [h.topic for h in history] == ["Java 多线程 · 内存可见性"]
    assert history[0].matched is True
    assert history[0].source_count == 4
    assert history[0].at


def test_history_dedups_same_topic_and_keeps_newest_first():
    retrieve.search_topic("主题甲")
    retrieve.search_topic("主题乙")
    retrieve.search_topic("主题甲")  # 同主题再搜 = 顶到最前，不新增
    assert [h.topic for h in settings.load_history()] == ["主题甲", "主题乙"]


def test_history_limit_is_capped():
    for i in range(settings.HISTORY_LIMIT + 5):
        settings.record_search(f"主题{i}", False, 0)
    assert len(settings.load_history()) == settings.HISTORY_LIMIT


def test_history_clear():
    settings.record_search("主题甲", True, 1)
    assert settings.clear_history() == []
    assert settings.load_history() == []


def test_empty_topic_is_not_recorded():
    retrieve.search_topic("   ")
    assert settings.load_history() == []


def test_preview_does_not_record_history():
    """`draft` 预演零副作用：搜索历史也不写。"""
    retrieve.search_topic("Java 多线程 · 内存可见性", allow_auto=False, record_history=False)
    assert settings.load_history() == []


def test_history_survives_module_writes():
    """模块/平台写盘不能抹掉历史（三段同住一个文件）。"""
    settings.record_search("主题甲", True, 1)
    settings.upsert_module(_new_module("模块乙"))
    settings.register_platforms([Source(name="知乎", type="社区", home="https://zhihu.com")])
    settings.remove_platform("zhihu.com")
    assert [h.topic for h in settings.load_history()] == ["主题甲"]


# ---------- 大小写不敏感（实测坑：搜 java 查不到 Java 的模块）----------


def test_registry_match_is_case_insensitive():
    """实测坑：`"java" in "Java 多线程"` 为 False → 用户打小写就查不到内置模块。"""
    for variant in ("java", "Java", "JAVA", "jAvA"):
        assert retrieve._from_registry([variant])[0], f"{variant} 应命中内置 java 模块"


def test_search_topic_is_case_insensitive():
    for variant in ("java", "JAVA", "Java 多线程"):
        r = retrieve.search_topic(variant)
        assert r["matched"] is True, f"{variant} 应命中"
        assert {x["origin"] for x in r["sources"]} == {"builtin"}


def test_user_module_match_is_case_insensitive():
    mid = settings.upsert_module(_new_module("Rust 所有权"))[0].id
    _add_entry(mid, "Rust 官方文档", "doc.rust-lang.org")
    assert retrieve.search_topic("rust")["matched"] is True
    assert retrieve.search_topic("RUST 所有权")["matched"] is True


def test_module_hit_by_topic_even_when_keywords_are_phrases(monkeypatch):
    """在线时 orient 出的是长短语（碰不上模块里的短词），必须靠 topic 精确命中缓存。

    否则「搜过的主题下次直接命中、不再烧 token」这条设计在线时形同失效。
    """
    from app.layers import topic as topic_mod

    mid = settings.upsert_module(_new_module("Transformer 架构"))[0].id
    _add_entry(mid, "Attention Is All You Need", "arxiv.org", "https://arxiv.org/abs/1706.03762")
    monkeypatch.setattr(
        topic_mod, "orient", lambda _t: ["自注意力与多头注意力的计算原理", "位置编码的作用"]
    )
    r = retrieve.search_topic("Transformer 架构")
    assert r["matched"] is True
    assert r["moduleId"] == mid
    assert [i["title"] for i in r["items"]] == ["Attention Is All You Need"]


def test_entity_normalize_is_case_insensitive():
    from app.layers.topology import normalize

    assert normalize("JMM 内存模型") == normalize("jmm内存模型")
