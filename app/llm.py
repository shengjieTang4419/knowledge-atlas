"""LLM 客户端（OpenAI 兼容：iFans / RelayRouter）+ **离线降级**。

设计要点：
- 无 key / 无网络时**不抛异常**，降级为确定性启发式（heuristic），保证整条链路离线可跑、可测。
- 凭据只从环境变量读，不落库；配置项见 `.env.example`。
- 只依赖 httpx，不引入各家 SDK（换网关只改 base_url）。

## 离线开关（给测试用，实测必需）
`is_online()` 读 `os.environ`，而 `.env` 由 `app/config.py` 在 **import 时**一次性灌入 ——
测试里 `monkeypatch.delenv("LLM_API_KEY")` **拦不住**：下一次 `is_online()` 仍为 True
（实测：用例真的发起了 API 调用，单例最慢 24s）。故提供显式开关 `set_offline()`。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from app.config import load_schema

__all__ = [
    "chat_json",
    "cheap_model",
    "embed_texts",
    "is_online",
    "relation_schema_hint",
    "resolve_backend",
    "set_offline",
]

_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "60"))

# 测试/离线强制开关：True 时覆盖一切判定，绝不发请求
_FORCE_OFFLINE = False


def set_offline(flag: bool = True) -> None:
    """强制离线（测试用）。设 True 后 is_online() 恒为 False。"""
    global _FORCE_OFFLINE
    _FORCE_OFFLINE = flag


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_backend() -> str:
    """有 key 走 api，否则离线 heuristic。"""
    if _FORCE_OFFLINE:
        return "heuristic"
    return "api" if _env("LLM_API_KEY") else "heuristic"


def is_online() -> bool:
    """是否具备真实 LLM 调用条件（只看配置，不发请求）。"""
    return resolve_backend() == "api"


def cheap_model() -> str:
    """轻任务用的低成本模型（走 .env 的 LLM_MODEL_CHEAP，回落到 LLM_MODEL）。"""
    return _env("LLM_MODEL_CHEAP") or _env("LLM_MODEL", "gpt-flash")


def _post(path: str, payload: dict[str, Any], *, base: str | None = None, key: str | None = None) -> dict[str, Any]:
    base = (base or _env("LLM_BASE_URL", "https://ingress.lfans.cn/v1")).rstrip("/")
    key = key or _env("LLM_API_KEY")
    resp = httpx.post(
        f"{base}{path}",
        json=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return data


def _extract_json(text: str) -> dict[str, Any]:
    """从模型输出里抠出第一个 JSON 对象（容忍 ```json 包裹与前后废话）。"""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = fence.group(1) if fence else None
    if raw is None:
        brace = re.search(r"\{.*\}", text, re.S)
        raw = brace.group(0) if brace else "{}"
    try:
        parsed: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed


def chat_json(system: str, user: str, *, model: str | None = None) -> dict[str, Any]:
    """让模型返回 JSON；失败或离线时返回 {}（调用方自行降级）。"""
    if not is_online():
        return {}
    try:
        data = _post(
            "/chat/completions",
            {
                "model": model or _env("LLM_MODEL", "gpt-flash"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "max_tokens": 2048,
            },
        )
        content = data["choices"][0]["message"]["content"] or ""
    except Exception:  # 网络/额度/协议异常一律降级，不让链路断
        return {}
    return _extract_json(content)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """调 embedding 接口；未配置则回落到确定性 stub（保持离线可跑）。"""
    base = _env("EMBEDDING_BASE_URL")
    key = _env("EMBEDDING_API_KEY")
    if _FORCE_OFFLINE or not (base and key):
        from app.rag.embed import embed as _stub

        return _stub(texts, backend="stub")
    data = _post(
        "/embeddings",
        {"model": _env("EMBEDDING_MODEL", "text-embedding-3-small"), "input": texts},
        base=base,
        key=key,
    )
    return [item["embedding"] for item in data["data"]]


def relation_schema_hint() -> str:
    """把 config/schema.yml 的关系判据渲染成给模型看的提示词片段。"""
    schema = load_schema()
    lines = ["关系类型（只允许以下三类）："]
    for name, spec in (schema.get("relations") or {}).items():
        desc, scope, direction = spec.get("desc", ""), spec.get("scope", ""), spec.get("direction", "")
        lines.append(f"- {name}：{desc}（范围：{scope}，方向：{direction}）")
    lines.append("- 无关：语义相近但既非前置也非同构机制")
    rules = schema.get("rules") or []
    if rules:
        lines.append("硬约束：")
        lines.extend(f"- {r}" for r in rules)
    return "\n".join(lines)
