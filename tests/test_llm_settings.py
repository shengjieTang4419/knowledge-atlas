"""模型资源配置验收（界面里改 provider / 降级链 / MoA）。

口径：`.env` 只做**播种**，界面存出来的 `data/settings/llm.json` **一旦存在即为唯一真源**
（成熟工具皆如此）。该文件在 `data/settings/` 下，已 gitignore。

三条硬约束：
1. 明文 Key **不回传**给界面（读接口只给 `hasKey` + 脱敏提示）；提交留空 = 不改；
2. provider 支持 `apiKeyEnv` **引用环境变量**（密钥不落盘）；
3. 链路顺序 = 尝试顺序；`moa` 模式多模型融合。
"""
import json

import pytest

from app import llm, settings


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """隔离配置目录；清掉本机 .env 灌进来的 LLM_* 变量，保证用例不依赖本机状态。"""
    monkeypatch.setattr(settings, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings, "LLM_CONFIG_PATH", tmp_path / "llm.json")
    monkeypatch.setattr(llm, "_FORCE_OFFLINE", False)
    for name in list(__import__("os").environ):
        if name.startswith("LLM_"):
            monkeypatch.delenv(name, raising=False)
    yield


def _seed_env(monkeypatch, chain: str = "gpt-plus,glm-flash") -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://ifans.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "ifans-key")
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "ifans")
    monkeypatch.setenv("LLM_CHAIN_MAIN", chain)


def _save(cfg: dict[str, object]) -> dict[str, object]:
    return settings.save_llm_config_payload(cfg)


# ---------- 播种：没有 llm.json 时按 .env 生成 ----------


def test_seeds_from_env_when_no_file(monkeypatch):
    _seed_env(monkeypatch)
    cfg = settings.llm_config_payload()
    assert cfg["source"] == "env", "没存过就是播种态"
    assert [p["id"] for p in cfg["providers"]] == ["ifans"]
    assert cfg["providers"][0]["apiKeyEnv"] == "LLM_API_KEY", "默认家的 Key 引用环境变量，不落盘"
    assert cfg["chains"]["main"]["entries"] == ["gpt-plus", "glm-flash"]
    assert cfg["chains"]["main"]["mode"] == "fallback"


def test_seed_skips_provider_without_base_url(monkeypatch):
    """没填 base_url 的家不进池——没填即不启用，对运行零影响。"""
    monkeypatch.setenv("LLM_PROVIDER_RELAY_API_KEY", "relay-key")
    monkeypatch.delenv("LLM_PROVIDER_RELAY_BASE_URL", raising=False)
    assert [p.id for p in settings.load_llm_config().providers] == []


def test_chain_mode_prefix_is_parsed(monkeypatch):
    _seed_env(monkeypatch, chain="moa:gpt-plus,glm-flash")
    chain = settings.load_llm_config().chains["main"]
    assert chain.mode == "moa"
    assert chain.entries == ["gpt-plus", "glm-flash"], "前缀要从链项里剥掉"


# ---------- 读写：明文 Key 不回传 ----------


def test_plain_key_is_never_returned(monkeypatch):
    _seed_env(monkeypatch)
    payload = settings.llm_config_payload()
    payload["providers"][0]["apiKey"] = "sk-secret-value-123456"
    payload["providers"][0]["apiKeyEnv"] = ""
    _save(payload)

    after = settings.llm_config_payload()
    assert after["source"] == "file"
    assert after["providers"][0]["apiKey"] == "", "明文 Key 绝不能回传给界面"
    assert after["providers"][0]["hasKey"] is True
    assert "sk-secret" not in json.dumps(after), "连脱敏提示里也不能出现完整 Key"
    assert "…" in after["providers"][0]["keyHint"]


def test_blank_key_keeps_previous(monkeypatch):
    """界面回显的 apiKey 恒为空串，所以「留空」必须是「不改」，否则一存就把 Key 抹了。"""
    _seed_env(monkeypatch)
    payload = settings.llm_config_payload()
    payload["providers"][0]["apiKey"] = "sk-keep-me-please-1234"
    payload["providers"][0]["apiKeyEnv"] = ""
    _save(payload)

    again = settings.llm_config_payload()
    again["providers"][0]["apiKey"] = ""  # 界面就是回显空串
    _save(again)

    raw = json.loads(settings.LLM_CONFIG_PATH.read_text(encoding="utf-8"))
    assert raw["providers"][0]["apiKey"] == "sk-keep-me-please-1234"


def test_saved_file_becomes_source_of_truth(monkeypatch):
    """存过之后 .env 改动不再影响——真源是文件（否则界面改完被 .env 悄悄覆盖）。"""
    _seed_env(monkeypatch)
    _save(settings.llm_config_payload())
    monkeypatch.setenv("LLM_CHAIN_MAIN", "别的模型")
    assert settings.load_llm_config().chains["main"].entries == ["gpt-plus", "glm-flash"]


def test_broken_file_falls_back_to_seed(monkeypatch):
    _seed_env(monkeypatch)
    settings.LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.LLM_CONFIG_PATH.write_text("{ 这不是 JSON", encoding="utf-8")
    cfg = settings.load_llm_config()
    assert cfg.source == "env"
    assert [p.id for p in cfg.providers] == ["ifans"]


# ---------- 链解析：顺序 / 跨家 / 无效项 ----------


def test_chain_resolves_provider_and_model(monkeypatch):
    _seed_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER_RELAY_BASE_URL", "https://relay.test/v1")
    monkeypatch.setenv("LLM_PROVIDER_RELAY_API_KEY", "relay-key")
    monkeypatch.setenv("LLM_CHAIN_MAIN", "gpt-plus,relay/deepseek-chat")
    chain = llm._chain("main")
    assert [(c.provider, c.model) for c in chain] == [
        ("ifans", "gpt-plus"),
        ("relay", "deepseek-chat"),
    ], "裸模型名归默认家，带斜杠的指定家"


def test_chain_skips_unresolvable_entry(monkeypatch):
    """家不存在 / 没 base_url / 有 base_url 但链上无 key —— 跳过而不是整条崩。"""
    _seed_env(monkeypatch, chain="gpt-plus,nope/gpt-x")
    chain = llm._chain("main")
    assert [(c.provider, c.model) for c in chain] == [("ifans", "gpt-plus")]


def test_is_online_requires_a_resolvable_chain(monkeypatch):
    """只有 base_url（没有链）不算「在线」：有家没有可调的东西。"""
    monkeypatch.setenv("LLM_BASE_URL", "https://ifans.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "ifans")
    assert llm.is_online() is False, "没有链 = 没有候选"
    monkeypatch.setenv("LLM_CHAIN_MAIN", "gpt-plus")
    assert llm.is_online() is True


def test_is_online_accepts_key_from_plain_field(monkeypatch):
    """界面里直接填明文 Key（不引用环境变量）也要算数。"""
    _seed_env(monkeypatch)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    payload = settings.llm_config_payload()
    payload["providers"][0]["apiKey"] = "sk-inline-123456"
    payload["providers"][0]["apiKeyEnv"] = ""
    _save(payload)
    assert llm.is_online() is True
    assert llm._chain("main")[0].api_key == "sk-inline-123456"


# ---------- MoA 融合 ----------


def _ok(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


def _moa_env(monkeypatch) -> None:
    _seed_env(monkeypatch, chain="moa:gpt-a,gpt-b")
    cfg = settings.llm_config_payload()
    cfg["providers"][0]["apiKey"] = "k"
    cfg["providers"][0]["apiKeyEnv"] = ""
    _save(cfg)


def test_moa_asks_every_candidate_and_unions_lists(monkeypatch):
    _moa_env(monkeypatch)
    seen: list[str] = []

    def fake_post(_path, payload, **_kw):  # type: ignore[no-untyped-def]
        seen.append(str(payload["model"]))
        if payload["model"] == "gpt-a":
            return _ok('{"keywords":["A","B"],"edge":"递进"}')
        return _ok('{"keywords":["B","C"],"edge":"递进"}')

    monkeypatch.setattr(llm, "_post", fake_post)
    out = llm.chat_json("s", "u")
    assert seen == ["gpt-a", "gpt-b"], "MoA 要把链上都问一遍"
    assert out["keywords"] == ["A", "B", "C"], "列表取并集去重"
    assert out["edge"] == "递进", "标量取多数票"
    assert llm.last_llm_route() == "ifans/gpt-a+ifans/gpt-b"


def test_moa_scalar_tie_prefers_chain_order(monkeypatch):
    """平票取链序靠前 = 配置里的优先级，别让「谁先答完」这种抖动决定结果。"""
    _moa_env(monkeypatch)

    def fake_post(_path, payload, **_kw):  # type: ignore[no-untyped-def]
        return _ok('{"edge":"递进"}' if payload["model"] == "gpt-a" else '{"edge":"无关"}')

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.chat_json("s", "u")["edge"] == "递进"


def test_moa_is_degraded_when_one_candidate_fails(monkeypatch):
    _moa_env(monkeypatch)

    def fake_post(_path, payload, **_kw):  # type: ignore[no-untyped-def]
        if payload["model"] == "gpt-a":
            raise RuntimeError("boom")
        return _ok('{"edge":"递进"}')

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.chat_json("s", "u")["edge"] == "递进"
    assert llm.last_llm_degraded() is True, "融合里少了一家 = 降级，必须可见"


def test_fallback_still_works_when_key_is_inline(monkeypatch):
    _seed_env(monkeypatch)
    payload = settings.llm_config_payload()
    payload["providers"][0]["apiKey"] = "k"
    payload["providers"][0]["apiKeyEnv"] = ""
    _save(payload)
    monkeypatch.setattr(llm, "_post", lambda *_a, **_k: _ok('{"ok":1}'))
    assert llm.chat_json("s", "u") == {"ok": 1}
    assert llm.last_llm_route() == "ifans/gpt-plus"
