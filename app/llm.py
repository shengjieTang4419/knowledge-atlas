"""LLM 客户端（OpenAI 兼容，**多家可并存 + 有界自动降级**）。

设计要点：
- 无 key / 无网络时**不抛异常**，降级为确定性启发式（heuristic），保证整条链路离线可跑、可测。
- 凭据只从环境变量读，不落库；配置项见 `.env.example`。
- 只依赖 httpx，不引入各家 SDK（换网关只改 base_url）。
- **资源层**：`.env` 里可配多家 provider，按 `LLM_CHAIN_*` 的顺序逐个试，第一个给出可用
  JSON 的就用它。判据借自 x_ai 的 `app/ai/router.py`（有界降级 + 只在"换一家可能更好"的
  错误上继续 + 降级可见），但其**设施**（Redis 健康、主动探针、熔断冷却、级联恢复）不搬——
  本仓是单进程同步 CLI，没有多副本、没有共享健康状态，那些机制在这里没有触发者。

## 离线开关（给测试用，实测必需）
`is_online()` 读 `os.environ`，而 `.env` 由 `app/config.py` 在 **import 时**一次性灌入 ——
测试里 `monkeypatch.delenv("LLM_API_KEY")` **拦不住**：下一次 `is_online()` 仍为 True
（实测：用例真的发起了 API 调用，单例最慢 24s）。故提供显式开关 `set_offline()`。
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from typing import Any, NamedTuple

import httpx

from app import settings
from app.config import load_schema

__all__ = [
    "chat_json",
    "embed_texts",
    "is_online",
    "last_llm_degraded",
    "last_llm_error",
    "last_llm_route",
    "probe",
    "relation_schema_hint",
    "resolve_backend",
    "set_offline",
]

_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "60"))

# 测试/离线强制开关：True 时覆盖一切判定，绝不发请求
_FORCE_OFFLINE = False

# 最近一次 chat_json 的结果（都失败时 error 非空；成功时 route 非空）。
# 为什么要有它们：chat_json 失败一律返回 {}（降级不让链路断），于是「网关 503」和
# 「模型确实没给出」在下游长得一模一样——实测被误报成「模型没抽出实体」。
_LAST_ERROR = ""
_LAST_ROUTE = ""
_LAST_DEGRADED = False


def last_llm_error() -> str:
    """最近一次 `chat_json` 的失败摘要（整条链都失败了才非空）。"""
    return _LAST_ERROR


def last_llm_route() -> str:
    """最近一次 `chat_json` 实际由谁服务（如 `ifans/gpt-plus`）；没成功则空串。"""
    return _LAST_ROUTE


def last_llm_degraded() -> bool:
    """最近一次是否发生了降级（链首没服务成、后面某个接住了）。"""
    return _LAST_DEGRADED


def set_offline(flag: bool = True) -> None:
    """强制离线（测试用）。设 True 后 is_online() 恒为 False。"""
    global _FORCE_OFFLINE
    _FORCE_OFFLINE = flag


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def resolve_backend() -> str:
    """有可用资源走 api，否则离线 heuristic。"""
    return "api" if is_online() else "heuristic"


def is_online() -> bool:
    """是否能真的发起调用（只看配置，不发请求）。

    判据 = **链上至少有一个能解析出 base_url + key 的候选**。只看「配了 key」不够：
    有 key 却没有链，等于没有可调的东西（配置残缺时界面比静默失败更该说话）。
    """
    if _FORCE_OFFLINE:
        return False
    cfg = settings.load_llm_config()
    return any(_candidates(cfg, tier) for tier in ("main", "cheap"))


class Candidate(NamedTuple):
    """一个可调用的「资源」= 家 + 模型（x_ai 的说法：provider/model）。"""

    provider: str
    base_url: str
    api_key: str
    model: str


def _candidates(cfg: settings.LlmConfig, tier: str) -> list[Candidate]:
    """把「配置」解析成「可调候选链」：链项写 `<model>`（用默认家）或 `<provider>/<model>`。

    解析不出的链项**跳过**（家不存在 / 没 base_url / 解析不出 key）——配置写错不该让整条链崩，
    但要知道哪项没生效：`llm-probe` 与设置页的「测试」会给出结论。
    """
    chain = cfg.chains.get(tier)
    if chain is None:
        return []
    providers = {p.id.lower(): p for p in cfg.providers}
    default_id = (cfg.default_provider or "").strip().lower()
    out: list[Candidate] = []
    for entry in chain.entries:
        pid, _, model = entry.partition("/")
        if not model:  # 裸模型名 = 默认家
            pid, model = default_id, pid
        provider = providers.get(pid.strip().lower())
        if provider is None or not model.strip() or not provider.base_url:
            continue
        key = provider.resolve_key()
        if key:
            out.append(Candidate(provider.id, provider.base_url.rstrip("/"), key, model.strip()))
    return out


def _chain(tier: str) -> list[Candidate]:
    """某档位的候选链（排查与测试用）。"""
    return _candidates(settings.load_llm_config(), tier)


def _post(path: str, payload: dict[str, Any], *, base: str, key: str, timeout: float) -> dict[str, Any]:
    resp = httpx.post(
        f"{base.rstrip('/')}{path}",
        json=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=timeout,
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


def chat_json(system: str, user: str, *, tier: str = "main") -> dict[str, Any]:
    """让模型返回 JSON：**按降级链逐个试**，第一个给出可用 JSON 的就用它。

    失败或离线时返回 {}（调用方自行降级）；结果记进 `last_llm_error()` /
    `last_llm_route()` / `last_llm_degraded()`，别把「调用失败」和「模型没给」混为一谈。

    降级判据（借 x_ai `router.py` §5.2 的两条）：
    - **继续降级**：超时 / 连不上 / 5xx / 429 / 401 / 模型不存在 / **空响应或非 JSON**；
      最后一条是本仓的实测补充——网关里确实有"HTTP 200 但 content 空"的模型。
    - **立即止损**：HTTP 400（我们自己的入参错）——换谁都会失败，白试一遍只是浪费时间。
    """
    global _LAST_ERROR, _LAST_ROUTE, _LAST_DEGRADED
    _LAST_ERROR = _LAST_ROUTE = ""
    _LAST_DEGRADED = False
    if not is_online():
        return {}
    cfg = settings.load_llm_config()
    chain = _candidates(cfg, tier)
    if not chain:
        _LAST_ERROR = (
            f"没有可用资源（检查 .env 的 LLM_BASE_URL / LLM_CHAIN_{tier.upper()}，"
            "或到「设置 · 模型」里配 provider 与链路）"
        )
        return {}
    budget = chain[: max(1, cfg.max_attempts)]
    mode = cfg.chains[tier].mode if tier in cfg.chains else "fallback"

    if mode == "moa":
        return _moa(budget, system, user, cfg.timeout)
    return _fallback(budget, system, user, cfg.timeout)


def _fallback(chain: list[Candidate], system: str, user: str, timeout: float) -> dict[str, Any]:
    """普通降级：逐个试，第一个给出可用 JSON 的就是它。"""
    global _LAST_ERROR, _LAST_ROUTE, _LAST_DEGRADED
    notes: list[str] = []
    for cand in chain:
        attempt = _ask(cand, system, user, timeout)
        if attempt.data:
            _LAST_ROUTE = f"{cand.provider}/{cand.model}"
            _LAST_DEGRADED = bool(notes)
            return attempt.data
        notes.append(attempt.note)
        if attempt.fatal:
            break
    _LAST_ERROR = "；".join(notes) or "降级链全部失败"
    return {}


def _moa(chain: list[Candidate], system: str, user: str, timeout: float) -> dict[str, Any]:
    """MoA（多模型融合）：链上前 N 个都问一遍，答案融合。

    代价与收益要摆明：一次业务打 N 次模型（成本 ×N、最坏耗时 ×N，均由 `maxAttempts` 封顶）。
    换来的是一致性——列表取并集提高召回，标量多数票降低单模型抖动。
    这条取舍与「人工审核」是配套的：**模型放宽召回，人来筛**。
    """
    global _LAST_ERROR, _LAST_ROUTE, _LAST_DEGRADED
    answers: list[dict[str, Any]] = []
    routes: list[str] = []
    notes: list[str] = []
    for cand in chain:
        attempt = _ask(cand, system, user, timeout)
        if attempt.data:
            answers.append(attempt.data)
            routes.append(f"{cand.provider}/{cand.model}")
            continue
        notes.append(attempt.note)
        if attempt.fatal:
            break
    if not answers:
        _LAST_ERROR = "；".join(notes) or "融合链全部失败"
        return {}
    _LAST_ROUTE = "+".join(routes)
    # 少于预期家数 = 有家没答上（融合是降级的，必须可见）
    _LAST_DEGRADED = len(answers) < len(chain) or bool(notes)
    return _fuse(answers)


class Attempt(NamedTuple):
    """一次提问的结果。`fatal` = 换一家也没用（我们自己的入参错）。"""

    data: dict[str, Any]
    note: str
    fatal: bool = False


def _ask(cand: Candidate, system: str, user: str, timeout: float) -> Attempt:
    tag = f"{cand.provider}/{cand.model}"
    try:
        data = _post(
            "/chat/completions",
            {
                "model": cand.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.0,
                "max_tokens": 2048,
            },
            base=cand.base_url,
            key=cand.api_key,
            timeout=timeout,
        )
        content = data["choices"][0]["message"]["content"] or ""
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 400:  # 入参错是我们的问题，不拿它惩罚供应商（也不浪费后续尝试）
            return Attempt({}, f"{tag}: HTTP 400 入参错，不降级：{e}", fatal=True)
        return Attempt({}, f"{tag}: HTTP {code}")
    except Exception as e:  # 网络/超时/DNS/TLS/协议异常一律换下一家
        return Attempt({}, f"{tag}: {type(e).__name__}")
    parsed = _extract_json(content)
    if not parsed:  # 有 JSON 才算这一家成了（实测网关里有 HTTP 200 但 content 空的模型）
        return Attempt({}, f"{tag}: 空响应或非 JSON")
    return Attempt(parsed, "")


def _sig(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _fuse(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """融合多模型答案。

    - **列表** → 并集去重（同一条只留一份）；
    - **标量** → 多数票，平票取**链序靠前**的（= 配置里的优先级）。

    不做语义级对齐：近义条目会各留一份。这是有意的——模型放宽召回，审核页的人来筛。
    """
    if len(answers) == 1:
        return answers[0]
    out: dict[str, Any] = {}
    for key in dict.fromkeys(k for a in answers for k in a):
        values = [a[key] for a in answers if key in a]
        if all(isinstance(v, list) for v in values):
            seen: set[str] = set()
            merged: list[Any] = []
            for value in values:
                for item in value:
                    sig = _sig(item)
                    if sig not in seen:
                        seen.add(sig)
                        merged.append(item)
            out[key] = merged
            continue
        counts: Counter[str] = Counter()
        first: dict[str, int] = {}
        for i, value in enumerate(values):
            sig = _sig(value)
            counts[sig] += 1
            first.setdefault(sig, i)
        best = sorted(counts, key=lambda s: (-counts[s], first[s]))[0]
        out[key] = next(v for v in values if _sig(v) == best)
    return out


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
        timeout=_TIMEOUT,
    )
    return [item["embedding"] for item in data["data"]]


def probe(tier: str = "main") -> list[dict[str, Any]]:
    """逐个真调一次，报告「谁能用、多快、为什么不能用」（设置页的「测试」按钮）。

    为什么不用 `GET /models` 那种零成本探针：实测网关上 `gpt-flash` **就在模型清单里**，
    但真实调用 503（上游账号挂了）。零成本探针会把它判成「可用」，用户拿到的仍是失败——
    **真实调用定生死**，这里就是真实调用。用户点一次才跑一次，成本可控。
    """
    cfg = settings.load_llm_config()
    chain = _candidates(cfg, tier)
    out: list[dict[str, Any]] = []
    for cand in chain[: max(1, cfg.max_attempts)]:
        started = time.monotonic()
        attempt = _ask(cand, "你是连通性探针。", '只输出 JSON：{"ok":1}', cfg.timeout)
        out.append(
            {
                "provider": cand.provider,
                "model": cand.model,
                "ok": bool(attempt.data),
                "ms": int((time.monotonic() - started) * 1000),
                "error": attempt.note,
            }
        )
    return out


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
