"""L1 · topic 定向：把一句主题拆成检索关键词。

例：输入「Java 多线程 · 内存可见性」→ 输出 ["Java 多线程", "内存可见性", "Java", "多线程"]
有 LLM 时用模型产出更准的词；离线走分隔符切分（确定性，可测）。
"""
from app.llm import chat_json, is_online

__all__ = ["orient"]

_SPLIT_RE = None


def _split_offline(topic: str) -> list[str]:
    """离线：按常见分隔符切，去掉空段，保序去重。"""
    import re

    parts = re.split(r"[·、,，/|;；\s]+", topic.strip())
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    # 整体主题也作为一个检索词（最贴合）
    whole = topic.strip()
    if whole and whole not in out:
        out.insert(0, whole)
    return out


def orient(topic: str) -> list[str]:
    """主题 → 检索关键词。"""
    topic = (topic or "").strip()
    if not topic:
        return []
    if is_online():
        # 不写死模型名：轻任务走 .env 的 LLM_CHAIN_CHEAP（有降级链，坏一个还有下一个）。
        # （曾写死 qwen-flash —— 它在 iFans 网关是 403 未购买，且绕过配置）
        data = chat_json(
            "你是学习主题拆解器。把主题拆成 3~6 个检索关键词（中英均可）。",
            f'主题：{topic}\n只输出 JSON：{{"keywords": ["...", "..."]}}',
            tier="cheap",
        )
        kws = data.get("keywords")
        if isinstance(kws, list) and kws:
            return [str(k).strip() for k in kws if str(k).strip()]
    return _split_offline(topic)
