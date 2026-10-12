"""可信源「搜索模块」验收。

核心口径（用户 2026-10-07 定的设计）：
1. 可信源**按 topic 组织成模块**，不是扁平列表；
2. 搜主题时 AI 判定 → **自动收录成模块**（下次同 topic 直接命中，不再烧 token）；
3. 设置页要能区分 AI 自动生成 / 手工添加。
"""
import json

import pytest

from app import llm, settings
from app.layers import retrieve
from app.models import Source


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    """只隔离设置目录（不污染真实 data/settings）。

    网络隔离由 tests/conftest.py 的全局 fixture 负责（清 LLM 环境变量）。
    """
    monkeypatch.setattr(settings, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "settings.json")
    yield


def _online_without_network(monkeypatch, sources: list[Source]) -> None:
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
    monkeypatch.setattr(retrieve, "_llm_sources", lambda topic, keywords: list(sources))


def _add_source(mid: str, name: str, stype: str = "博客", **kw: str) -> list[settings.TrustedModule]:
    return settings.add_module_source(mid, Source(name=name, type=stype, **kw))  # type: ignore[arg-type]


def _new_module(topic: str, origin: str = "manual", keywords: list[str] | None = None) -> settings.TrustedModule:
    return settings.TrustedModule(
        id=settings.module_id(topic), topic=topic, origin=origin, keywords=keywords or [topic]
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


def test_add_and_remove_source_in_module():
    mid = settings.upsert_module(_new_module("Rust"))[0].id
    _add_source(mid, "Rust 官方文档", "规范", locator="https://doc.rust-lang.org/")
    assert [s.name for s in settings.load_modules()[0].sources] == ["Rust 官方文档"]
    # 同名覆盖
    _add_source(mid, "Rust 官方文档", "书籍")
    mods = settings.load_modules()
    assert len(mods[0].sources) == 1
    assert mods[0].sources[0].type == "书籍"
    # 删除
    settings.remove_module_source(mid, "Rust 官方文档")
    assert settings.load_modules()[0].sources == []


def test_manual_edit_flips_origin_to_manual():
    """AI 生成的模块被我手工改过之后，就标成 manual（不该再被当纯自动）。"""
    mid = settings.upsert_module(_new_module("AI 主题", origin="auto"))[0].id
    _add_source(mid, "我补的源", "博客")
    assert settings.load_modules()[0].origin == "manual"


def test_add_source_to_missing_module_raises():
    with pytest.raises(KeyError):
        _add_source("不存在的模块", "x")


def test_delete_module():
    settings.upsert_module(_new_module("A"))
    settings.upsert_module(_new_module("B"))
    left = settings.delete_module(settings.module_id("A"))
    assert [m.topic for m in left] == ["B"]
    assert settings.delete_module("不存在") is not None  # 幂等，不抛


def test_match_modules_by_topic_keyword_source_name():
    mid = settings.upsert_module(_new_module("Rust 所有权"))[0].id
    _add_source(mid, "Rust 官方文档", "规范")
    assert [m.topic for m in settings.match_modules(["Rust"])] == ["Rust 所有权"]
    assert [m.topic for m in settings.match_modules(["所有权"])] == ["Rust 所有权"]
    assert settings.match_modules(["园艺", "种花"]) == []


def test_corrupt_settings_file_is_tolerated():
    settings.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text("{坏 json", encoding="utf-8")
    assert settings.load_modules() == []


def test_legacy_flat_format_is_migrated():
    """旧格式（扁平 trusted_sources）不丢数据：迁成一个手工模块。"""
    settings.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SETTINGS_PATH.write_text(
        json.dumps({"trusted_sources": [{"name": "老源", "type": "规范", "why": "", "locator": ""}]}),
        encoding="utf-8",
    )
    mods = settings.load_modules()
    assert len(mods) == 1
    assert mods[0].origin == "manual"
    assert [s.name for s in mods[0].sources] == ["老源"]


# ---------- 搜索编排 ----------


def test_search_hits_builtin_first():
    r = retrieve.search_topic("Java 多线程 · 内存可见性")
    assert r["matched"] is True
    assert {s["origin"] for s in r["sources"]} == {"builtin"}
    assert r["autoCollected"] is False


def test_search_hits_user_module():
    mid = settings.upsert_module(_new_module("Rust 所有权"))[0].id
    _add_source(mid, "Rust 官方文档", "规范")
    r = retrieve.search_topic("Rust 所有权")
    assert r["matched"] is True
    assert r["sources"][0]["origin"] == "manual"
    assert r["moduleId"] == mid


def test_search_no_match_reports_needs_config():
    r = retrieve.search_topic("园艺种花")
    assert r["matched"] is False
    assert r["needsConfig"] is True
    assert r["moduleCount"] == 0


def test_search_auto_collects_module_with_llm(monkeypatch):
    """AI 判定 → 自动收录成 auto 模块（核心诉求）。"""
    _online_without_network(
        monkeypatch,
        [
            Source(name="Rust 官方文档", type="规范", locator="https://doc.rust-lang.org/"),
            Source(name="Rust 源码", type="源码"),
        ],
    )
    monkeypatch.setattr(
        retrieve,
        "_llm_sources",
        lambda topic, keywords: [
            Source(name="Rust 官方文档", type="规范", locator="https://doc.rust-lang.org/"),
            Source(name="Rust 源码", type="源码"),
        ],
    )
    r = retrieve.search_topic("Rust 所有权")
    assert r["matched"] is True
    assert r["autoCollected"] is True
    assert {s["origin"] for s in r["sources"]} == {"auto"}

    # 已落盘，且标为 auto
    mods = settings.load_modules()
    assert len(mods) == 1
    assert mods[0].origin == "auto"
    assert [s.name for s in mods[0].sources][0] == "Rust 官方文档", "规范应排最前"


def test_second_search_hits_collected_module_without_llm(monkeypatch):
    """第二次搜同主题：直接命中已收录模块，不再调模型（落盘即缓存）。"""
    _online_without_network(
        monkeypatch,
        [
            Source(name="Rust 官方文档", type="规范", locator="https://doc.rust-lang.org/"),
            Source(name="Rust 源码", type="源码"),
        ],
    )
    calls = {"n": 0}

    def fake_llm(topic: str, keywords: list[str]) -> list[Source]:
        calls["n"] += 1
        return [Source(name="Rust 官方文档", type="规范")]

    _online_without_network(monkeypatch, [Source(name="Rust 官方文档", type="规范")])
    monkeypatch.setattr(retrieve, "_llm_sources", fake_llm)
    retrieve.search_topic("Rust 所有权")
    assert calls["n"] == 1

    # 第二次：即使 LLM 不可用，也应命中模块
    # 关掉在线（模拟「模型不可用」）：仍应命中已收录的模块
    monkeypatch.setattr(llm, "_FORCE_OFFLINE", True)
    r = retrieve.search_topic("Rust 所有权")
    assert r["matched"] is True
    assert r["autoCollected"] is False, "第二次是缓存命中，不是新收录"
    assert calls["n"] == 1, "不该再调模型"


def test_auto_collect_skips_save_when_llm_returns_nothing(monkeypatch):
    """模型没给出合法源 → 不落盘（不污染设置）。"""
    _online_without_network(
        monkeypatch,
        [
            Source(name="Rust 官方文档", type="规范", locator="https://doc.rust-lang.org/"),
            Source(name="Rust 源码", type="源码"),
        ],
    )
    _online_without_network(monkeypatch, [])
    r = retrieve.search_topic("冷门主题")
    assert r["matched"] is False
    assert r["needsConfig"] is True
    assert settings.load_modules() == []


def test_allow_auto_false_never_calls_llm(monkeypatch):
    _online_without_network(
        monkeypatch,
        [
            Source(name="Rust 官方文档", type="规范", locator="https://doc.rust-lang.org/"),
            Source(name="Rust 源码", type="源码"),
        ],
    )

    def boom(topic: str, keywords: list[str]) -> list[Source]:
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


# ---------- 大小写不敏感（实测坑：搜 java 查不到 Java 的模块）----------


def test_registry_match_is_case_insensitive():
    """实测坑：`"java" in "Java 多线程"` 为 False → 用户打小写就查不到内置模块。"""
    for variant in ("java", "Java", "JAVA", "jAvA"):
        assert retrieve._from_registry([variant]), f"{variant} 应命中内置 java 模块"


def test_search_topic_is_case_insensitive():
    for variant in ("java", "JAVA", "Java 多线程"):
        r = retrieve.search_topic(variant)
        assert r["matched"] is True, f"{variant} 应命中"
        assert {x["origin"] for x in r["sources"]} == {"builtin"}


def test_user_module_match_is_case_insensitive():
    mid = settings.upsert_module(_new_module("Rust 所有权"))[0].id
    _add_source(mid, "Rust 官方文档", "规范")
    assert retrieve.search_topic("rust")["matched"] is True
    assert retrieve.search_topic("RUST 所有权")["matched"] is True


def test_entity_normalize_is_case_insensitive():
    from app.layers.topology import normalize

    assert normalize("JMM 内存模型") == normalize("jmm内存模型")
