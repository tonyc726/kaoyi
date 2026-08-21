from __future__ import annotations

from collections.abc import Callable

from adapters import (
    aliyun,
    claude,
    cursor,
    grok,
    minimax,
    openai,
    openrouter,
    volcengine,
    volcengine_agent,
    zhipu,
)
from kaoyi.models import Snapshot

FetchFn = Callable[[], Snapshot]

REGISTRY: dict[str, FetchFn] = {
    "zhipu": zhipu.fetch,
    "minimax": minimax.fetch,
    "volcengine": volcengine.fetch,
    "volcengine-agent": volcengine_agent.fetch,
    "aliyun": aliyun.fetch,
    "cursor": cursor.fetch,
    "claude": claude.fetch,
    "grok": grok.fetch,
    "openai": openai.fetch,
    "openrouter": openrouter.fetch,
}
