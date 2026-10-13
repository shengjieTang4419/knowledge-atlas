"""CLI 契约：draft（端到端预演，不写盘）与 commit（写盘）的 JSON 形状；
以及搜主题 / 历史 / 平台 / 条目四条界面用的 JSON 契约。

离线确定性路径：`set_offline(True)` 强制走离线启发式（conftest 只在 socket 层禁网，
`is_online()` 因 .env 有 key 仍为 True，故这里显式关掉，保证确定性、可测）。
"""
import json

import pytest

from app import settings
from app.cli import _apply_draft, main
from app.llm import set_offline


@pytest.fixture(autouse=True)
def _offline():
    set_offline(True)
    yield
    set_offline(False)


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path, monkeypatch):
    """界面用的那几条命令会写 `data/settings/settings.json`：隔离到 tmp（别污染真库）。"""
    monkeypatch.setattr(settings, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "settings.json")
    yield


def test_draft_returns_json_contract(capsys):
    rc = main(["draft", "Java 多线程 · 内存可见性"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["topic"] == "Java 多线程 · 内存可见性"
    assert data["matched"] is True
    assert data["keywords"]
    assert data["entities"], "离线应解析现有 wiki 出实体"
    for key in ("sources", "items", "relations", "cards", "edges"):
        assert key in data, f"draft 结果缺字段 {key}"
    # 两层口径：条目必须挂在某个命中的平台上
    assert {i["source"] for i in data["items"]} <= {s["id"] for s in data["sources"]}
    assert isinstance(data["edges"], list)
    assert all(e["type"] in {"递进", "应用"} for e in data["edges"])


def test_draft_unknown_topic_needs_config(capsys):
    rc = main(["draft", "一个不存在的主题xyz"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["matched"] is False
    assert data["needsConfig"] is True
    assert data["entities"] == []


def test_search_json_contract_and_history(capsys):
    """`search --json` 两层形状 + 顺带把历史写下来（界面侧栏靠它）。"""
    rc = main(["search", "Java 多线程 · 内存可见性", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data["matched"] is True
    assert data["sources"][0]["id"] and data["sources"][0]["home"]
    assert data["items"][0]["title"] and data["items"][0]["source"]

    rc = main(["history", "--json"])
    history = json.loads(capsys.readouterr().out)["history"]
    assert rc == 0
    assert [h["topic"] for h in history] == ["Java 多线程 · 内存可见性"]
    assert history[0]["matched"] is True and history[0]["at"]

    main(["history-clear", "--json"])
    assert json.loads(capsys.readouterr().out)["history"] == []


def test_platform_add_remove_json_contract(capsys):
    rc = main(
        ["platform-add", "--name", "知乎", "--type", "社区", "--home", "https://zhihu.com", "--json"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["platform"]["id"] == "zhihu.com"
    assert payload["platform"]["name"] == "知乎"
    assert payload["platform"]["origin"] == "manual"
    assert "zhihu.com" in {p["id"] for p in payload["platforms"]}

    main(["platform-remove", "--id", "zhihu.com", "--json"])
    platforms = json.loads(capsys.readouterr().out)["platforms"]
    assert "zhihu.com" not in {p["id"] for p in platforms}


def test_platform_add_reports_collapsed_platform(capsys):
    """同站归入已有平台时，回报的必须是**归一后那条**——界面据此说实话（否则会显示 `id —`）。"""
    main(["platform-add", "--name", "GitHub 副本", "--type", "博客", "--home", "https://github.com", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["platform"]["id"] == "github.com"
    assert payload["platform"]["name"] == "GitHub", "内置平台先到先得"
    assert payload["platform"]["type"] == "源码", "不该被后来的「博客」覆盖"


def test_platform_add_rejects_unknown_type(capsys):
    rc = main(["platform-add", "--name", "X", "--type", "瞎写", "--json"])
    assert rc == 2
    assert "未知来源类型" in capsys.readouterr().err


def test_entry_add_remove_json_contract(capsys):
    main(["module-save", "--topic", "Rust 所有权", "--json"])
    capsys.readouterr()
    main(
        [
            "entry-add",
            "--module",
            settings.module_id("Rust 所有权"),
            "--title",
            "Rust Reference",
            "--source",
            "doc.rust-lang.org",
            "--locator",
            "https://doc.rust-lang.org/reference/",
            "--json",
        ]
    )
    modules = json.loads(capsys.readouterr().out)["modules"]
    assert modules[0]["items"] == [
        {
            "title": "Rust Reference",
            "source": "doc.rust-lang.org",
            "locator": "https://doc.rust-lang.org/reference/",
            "note": "",
        }
    ]

    main(["entry-remove", "--module", settings.module_id("Rust 所有权"), "--title", "Rust Reference", "--json"])
    assert json.loads(capsys.readouterr().out)["modules"][0]["items"] == []


def test_entry_add_to_missing_module_exits_2(capsys):
    rc = main(["entry-add", "--module", "不存在", "--title", "X", "--json"])
    assert rc == 2
    assert "模块不存在" in capsys.readouterr().err


def test_apply_draft_writes_entities_only(tmp_path):
    """_apply_draft 解析 camelCase 键（oneLine）并写 wiki 卡；cards/edges 为空时不落盘。"""
    draft = {
        "topic": "测试主题",
        "sources": [{"name": "源A", "type": "博客", "why": "", "home": "https://example.com"}],
        "entities": [{"name": "甲实体", "type": "概念", "oneLine": "甲的一句话"}],
        "relations": [],
        "cards": [],
        "edges": [],
    }
    result = _apply_draft(draft, notes_dir=tmp_path)
    assert result == {"writtenEntities": ["甲实体"], "cards": 0, "edges": 0}
    assert (tmp_path / "甲实体.md").exists()
    assert "甲的一句话" in (tmp_path / "甲实体.md").read_text(encoding="utf-8")
