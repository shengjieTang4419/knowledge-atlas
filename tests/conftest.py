"""pytest 全局配置。

1. 把项目根加入 import 路径（等价于 pyproject 的 `pythonpath=["."]`）；
2. **全局禁网**：测试期间一切外部连接立即失败，绝不发真实请求。

## 为什么在 socket 层禁网（三次踩坑后的结论）
本机 `.env` 一配 `LLM_API_KEY`，`is_online()` 就为 True，于是
`orient()` / `judge()` / `search_topic()` 会真的调模型。三种"看起来对"的拦截都失败过：

| 做法 | 为什么拦不住 |
|---|---|
| `monkeypatch.delenv("LLM_API_KEY")` | `.env` 由 `app/config.py` 在 import 时
  `load_dotenv` 灌进 `os.environ`，删了当次、下次仍在 |
| `monkeypatch.setattr(retrieve, "is_online", ...)` | 各模块
  `from app.llm import is_online` 是**独立绑定**，patch 一处管不到另一处 |
| `monkeypatch.setattr(llm, "chat_json", ...)` | 同上：`topic.py` 在 import 时
  已持有**原始函数对象**，改 `llm` 的属性对它无效 |

实测代价：整套用例 0.2s → 45s，单例最慢 24s，且结果依赖模型输出（同一份代码时绿时红）。

**根治**：在 `socket.connect` 上拦住所有非本机连接 → 不管谁调、走哪种绑定，都瞬间失败。
`chat_json` 内部本就 `except Exception: return {}`（优雅降级），故拦网后自动退回离线路径。

需要真实网络的测试请标 `@pytest.mark.allow_network`。
"""
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_LOCAL = {"127.0.0.1", "::1", "localhost"}
_orig_connect = socket.socket.connect


def _guard_connect(self, address):  # type: ignore[no-untyped-def]
    host = address[0] if isinstance(address, tuple) and address else ""
    if isinstance(host, str) and host not in _LOCAL:
        raise RuntimeError(f"测试期禁网：拦截到外部连接 {address!r}")
    return _orig_connect(self, address)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch, request):  # type: ignore[no-untyped-def]
    """默认禁网；标了 allow_network 的用例放行。"""
    if request.node.get_closest_marker("allow_network"):
        yield
        return
    monkeypatch.setattr(socket.socket, "connect", _guard_connect)
    yield


def pytest_configure(config):  # type: ignore[no-untyped-def]
    config.addinivalue_line("markers", "allow_network: 允许该用例发起真实网络连接")
