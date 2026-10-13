"""LLM 资源层验收：有界自动降级 + 失败/降级可见。

三条判据（借 x_ai `app/ai/router.py`，设施不借）：
1. 按 `.env` 链顺序试，**第一个给出可用 JSON 的**就用它；
2. 只在「换一家可能更好」的错误上继续降级（超时/5xx/429/401/模型不存在/空响应）；
3. 降级必须可见（`last_llm_route` / `last_llm_degraded`）。

为什么需要可见性：`chat_json` 失败一律返回 `{}`（降级不让链路断），于是「网关 503」和
「模型确实没给出」在下游长得一模一样——实测被误报成「模型没抽出实体」，排查白走一大圈。
"""
import httpx
import pytest

from app import llm, settings


@pytest.fixture
def _online(monkeypatch, tmp_path):
    """两家、三条链的确定性环境（不碰真实网络、不读本机 llm.json）。"""
    monkeypatch.setattr(llm, "_FORCE_OFFLINE", False)
    # 关键隔离：load_llm_config 优先读 data/settings/llm.json（界面存过即真源）。
    # 不把它指到临时空文件，用例会读到开发者本机真实链（如 deepseek-flash,glm-flash,glm-pro），
    # 链首就不是下面声明的 gpt-plus，降级顺序断言全错（实测 6 用例全挂）。
    monkeypatch.setattr(settings, "LLM_CONFIG_PATH", tmp_path / "llm.json")
    monkeypatch.setenv("LLM_BASE_URL", "https://ifans.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "ifans-key")
    monkeypatch.setenv("LLM_DEFAULT_PROVIDER", "ifans")
    monkeypatch.setenv("LLM_PROVIDER_RELAY_BASE_URL", "https://relay.test/v1")
    monkeypatch.setenv("LLM_PROVIDER_RELAY_API_KEY", "relay-key")
    monkeypatch.setenv("LLM_CHAIN_MAIN", "gpt-plus,deepseek-flash,relay/deepseek-chat")
    monkeypatch.delenv("LLM_CHAIN_CHEAP", raising=False)


def _ok(content: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": content}}]}


def _http_error(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://x.test/v1/chat/completions")
    return httpx.HTTPStatusError("boom", request=req, response=httpx.Response(code, request=req))


def test_chain_is_syntax_and_missing_key_aware(_online, monkeypatch):
    """`relay` 没有 key 时不该进池；裸模型名归默认家。"""
    monkeypatch.delenv("LLM_PROVIDER_RELAY_API_KEY", raising=False)
    chain = llm._chain("main")
    assert [(c.provider, c.model) for c in chain] == [
        ("ifans", "gpt-plus"),
        ("ifans", "deepseek-flash"),
    ], "缺 key 的家必须被剔除"


def test_falls_over_to_next_and_reports_degradation(_online, monkeypatch):
    calls: list[str] = []

    def fake_post(_path, payload, **_kw):  # type: ignore[no-untyped-def]
        calls.append(str(payload["model"]))
        if payload["model"] == "gpt-plus":
            raise _http_error(503)
        return _ok('{"entities":[{"name":"Transformer"}]}')

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.chat_json("s", "u")["entities"][0]["name"] == "Transformer"
    assert calls == ["gpt-plus", "deepseek-flash"], "按链顺序试，成功了就不再打后面的"
    assert llm.last_llm_route() == "ifans/deepseek-flash"
    assert llm.last_llm_degraded() is True
    assert llm.last_llm_error() == ""


def test_head_success_is_not_degraded(_online, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda *_a, **_k: _ok('{"ok":1}'))
    assert llm.chat_json("s", "u") == {"ok": 1}
    assert llm.last_llm_route() == "ifans/gpt-plus"
    assert llm.last_llm_degraded() is False


def test_empty_content_falls_over(_online, monkeypatch):
    """实测踩坑：网关里有模型 HTTP 200 但 content 是空的（glm-*），必须换下一家。"""
    seen: list[str] = []

    def fake_post(_path, payload, **_kw):  # type: ignore[no-untyped-def]
        seen.append(str(payload["model"]))
        return _ok("") if payload["model"] == "gpt-plus" else _ok('{"ok":2}')

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.chat_json("s", "u") == {"ok": 2}
    assert seen == ["gpt-plus", "deepseek-flash"]


def test_request_error_stops_immediately(_online, monkeypatch):
    """HTTP 400 是我们自己的入参错：换谁都会失败，白试一遍只是浪费时间。"""
    seen: list[str] = []

    def fake_post(_path, payload, **_kw):  # type: ignore[no-untyped-def]
        seen.append(str(payload["model"]))
        raise _http_error(400)

    monkeypatch.setattr(llm, "_post", fake_post)
    assert llm.chat_json("s", "u") == {}
    assert seen == ["gpt-plus"], "400 不该继续降级"
    assert "不降级" in llm.last_llm_error()


def test_all_failed_reports_every_attempt(_online, monkeypatch):
    monkeypatch.setattr(llm, "_post", lambda *_a, **_k: (_ for _ in ()).throw(_http_error(503)))
    assert llm.chat_json("s", "u") == {}
    assert llm.last_llm_route() == ""
    err = llm.last_llm_error()
    assert err.count("HTTP 503") == 3, f"三个候选都要记进摘要：{err}"


def test_attempts_are_bounded(_online, monkeypatch):
    """有界降级：链再长也不会无限打（LLM_MAX_ATTEMPTS）。"""
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "2")
    seen: list[str] = []
    monkeypatch.setattr(
        llm, "_post", lambda _p, payload, **_k: (seen.append(str(payload["model"])), _http_error(500))[1]
    )
    assert llm.chat_json("s", "u") == {}
    assert seen == ["gpt-plus", "deepseek-flash"]


def test_offline_is_not_an_error(monkeypatch):
    """离线是配置状态，不是失败——别把「没配 key」显示成「模型调用失败」。"""
    monkeypatch.setattr(llm, "_post", lambda *_a, **_k: pytest.fail("离线不该发请求"))
    llm.set_offline(True)
    try:
        assert llm.chat_json("s", "u") == {}
        assert llm.last_llm_error() == ""
        assert llm.last_llm_route() == ""
    finally:
        llm.set_offline(False)
