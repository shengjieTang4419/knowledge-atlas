"""配置加载：读 config/ 下的 yml + 载入 .env。凭据只走环境变量，不落库。

**为什么在这里 load_dotenv**（实测踩坑）：
依赖里装了 `python-dotenv`，但代码里从没调用它 —— 于是 `.env` 里写了 key 也读不到，
`is_online()` 恒为 False，界面一直提示「没配 AI 模型 Key」。
放在本模块顶部：`app.config` 是所有入口（cli / llm / layers）的第一跳，覆盖面无死角。
"""
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]   # knowledge-atlas/
CONFIG = ROOT / "config"
DATA = ROOT / "data"

# 不覆盖已存在的环境变量（CI/容器里显式 export 的优先级更高）
load_dotenv(ROOT / ".env", override=False)


def load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_sources() -> dict[str, Any]:
    """可信源注册表 + 可信度分级。"""
    return load_yaml("sources.yml")


def load_schema() -> dict[str, Any]:
    """实体类型 + 关系 schema（递进/借鉴）。"""
    return load_yaml("schema.yml")
