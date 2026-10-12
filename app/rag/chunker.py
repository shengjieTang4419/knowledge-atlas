"""nanoRAG · L0 分块。

把 markdown 切成「带标题上下文」的块，喂给后面所有层。

契约（先读 test_chunker.py 再实现）：
1. 按 markdown 标题（# 开头的行）分段；每块记录它所属的标题路径 heading_path。
2. 一个标题段若超过 max_chars，按 max_chars 切块，块与块之间 overlap 个字符重叠。
3. L0 先暴力：不强求句边界（句边界是 L0.5 的优化）。
4. 空文本返回空列表。
"""
import re
from dataclasses import dataclass, field

__all__ = ["Chunk", "chunk_markdown"]

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass
class Chunk:
    text: str
    heading_path: list[str] = field(default_factory=list)  # 该块所属标题层级，如 ['Embedding 是什么', '是什么（骨架）']
    source: str = ""                                        # 来源文件
    seq: int = 0                                            # 块序号（按全文顺序）


def _split_sections(text: str) -> list[tuple[list[str], str]]:
    """按标题切段 → [(heading_path, section_text)]；section_text 含标题行（让块自含上下文）。"""
    sections: list[tuple[list[str], str]] = []
    titles: list[str] = []
    levels: list[int] = []
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append((list(titles), body))
        buf.clear()

    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            while levels and levels[-1] >= level:  # 回退到同级或更高层
                levels.pop()
                titles.pop()
            levels.append(level)
            titles.append(m.group(2).strip())
            buf.append(titles[-1])
        else:
            buf.append(line)
    flush()
    return sections


def _window(body: str, max_chars: int, overlap: int) -> list[str]:
    """定长滑窗切块；step = max_chars - overlap（至少 1，防死循环）。"""
    if len(body) <= max_chars:
        return [body]
    step = max(1, max_chars - overlap)
    windows: list[str] = []
    start = 0
    while start < len(body):
        end = min(start + max_chars, len(body))
        windows.append(body[start:end])
        if end == len(body):
            break
        start += step
    return windows


def chunk_markdown(text: str, *, source: str = "", max_chars: int = 500, overlap: int = 50) -> list[Chunk]:
    """按标题分段、段内定长切块、块间重叠。

    Args:
        text: markdown 全文。
        source: 来源标记（文件名等），透传到 Chunk.source。
        max_chars: 单块最大字符数。
        overlap: 相邻块重叠的字符数。

    Returns:
        Chunk 列表，seq 从 0 递增。
    """
    chunks: list[Chunk] = []
    for heading_path, body in _split_sections(text):
        for piece in _window(body, max_chars, overlap):
            chunks.append(Chunk(text=piece, heading_path=list(heading_path), source=source, seq=len(chunks)))
    return chunks
