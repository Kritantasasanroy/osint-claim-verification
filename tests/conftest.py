from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from fakes import Handler
from osint_harness.settings import Settings, TokenPrice
from osint_harness.transport import ResponseCache, Transport


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        nvidia_api_key="test-nvidia",
        tavily_api_key="test-tavily",
        llm_model="test/llm",
        ocr_model="test/ocr",
        embedding_model="test/embed",
        llm_reasoning=False,
        max_concurrent_requests=2,
        price=TokenPrice(input_per_mtok=1.0, output_per_mtok=2.0),
        cache_path=tmp_path / "cache.sqlite3",
    )


@pytest.fixture
def make_transport() -> Callable[[Handler], Transport]:
    def build(handler: Handler) -> Transport:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return Transport(client, ResponseCache.disabled(), max_concurrency=2, backoff_s=0.0)

    return build
