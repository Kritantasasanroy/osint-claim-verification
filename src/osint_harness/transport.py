import asyncio
import hashlib
import json
import math
import random
import sqlite3
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import httpx
from pydantic import BaseModel, JsonValue, ValidationError


class ServiceUnavailable(RuntimeError):
    def __init__(self, url: str, detail: str) -> None:
        super().__init__(f"{url} kept failing after retries: {detail}")


class ServiceRejected(RuntimeError):
    def __init__(self, url: str, status: int, body: str) -> None:
        super().__init__(f"{url} rejected the request with HTTP {status}: {body[:400]}")
        self.status = status


@dataclass(frozen=True)
class HttpReply:
    text: str
    latency_s: float
    cached: bool


class ResponseCache:
    """Successful responses keyed by request, so re-running a benchmark is reproducible and free."""

    def __init__(self, path: Path) -> None:
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute("CREATE TABLE IF NOT EXISTS replies (key TEXT PRIMARY KEY, text TEXT, latency REAL)")

    @classmethod
    def disabled(cls) -> "ResponseCache":
        return cls(Path(":memory:"))

    def lookup(self, key: str) -> HttpReply | None:
        row = self._db.execute("SELECT text, latency FROM replies WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return HttpReply(text=row[0], latency_s=row[1], cached=True)

    def forget(self, key: str) -> None:
        self._db.execute("DELETE FROM replies WHERE key = ?", (key,))
        self._db.commit()

    def store(self, key: str, reply: HttpReply) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO replies VALUES (?, ?, ?)", (key, reply.text, reply.latency_s)
        )
        self._db.commit()


class AdaptiveLimiter:
    """Concurrency for one host that backs off together and recovers slowly.

    When the service pushes back (HTTP 429/5xx, a timeout) the limit halves and the whole host waits out a
    shared cooldown, so four workers do not each retry into a throttled API on their own schedule. After ten
    clean replies the limit grows by one, back up to the ceiling. This is AIMD, as in TCP congestion control.
    """

    RECOVER_AFTER: ClassVar[int] = 10

    def __init__(self, ceiling: int) -> None:
        self.ceiling = ceiling
        self.limit = ceiling
        self._in_flight = 0
        self._clean = 0
        self._cool_until = 0.0
        self._changed = asyncio.Condition()

    async def __aenter__(self) -> None:
        async with self._changed:
            while True:
                pause = self._cool_until - time.monotonic()
                if self._in_flight < self.limit and pause <= 0:
                    self._in_flight += 1
                    return
                try:
                    await asyncio.wait_for(self._changed.wait(), timeout=pause if pause > 0 else None)
                except TimeoutError:
                    continue

    async def __aexit__(self, *_: object) -> None:
        async with self._changed:
            self._in_flight -= 1
            self._changed.notify_all()

    def succeeded(self) -> None:
        self._clean += 1
        if self._clean >= self.RECOVER_AFTER and self.limit < self.ceiling:
            self.limit += 1
            self._clean = 0

    def throttled(self, pause_s: float) -> None:
        self.limit = max(1, self.limit // 2)
        self._clean = 0
        self._cool_until = max(self._cool_until, time.monotonic() + pause_s)


class Transport:
    """Every outbound HTTP call: per-host adaptive concurrency, retry on transient failure, response cache."""

    RETRYABLE_STATUS: ClassVar[frozenset[int]] = frozenset({429, 500, 502, 503, 504})
    MAX_ATTEMPTS: ClassVar[int] = 10
    MAX_WAIT_S: ClassVar[float] = 120.0

    def __init__(
        self,
        client: httpx.AsyncClient,
        cache: ResponseCache,
        max_concurrency: int,
        backoff_s: float = 1.0,
        cache_by_default: bool = True,
    ) -> None:
        self._client = client
        self._backoff_s = backoff_s
        self._cache = cache
        self._cache_by_default = cache_by_default
        self._ceiling = max_concurrency
        self._limiters: dict[str, AdaptiveLimiter] = {}

    def limiter(self, url: str) -> AdaptiveLimiter:
        host = httpx.URL(url).host
        if host not in self._limiters:
            self._limiters[host] = AdaptiveLimiter(self._ceiling)
        return self._limiters[host]

    async def post(
        self, url: str, payload: JsonValue, headers: Mapping[str, str], use_cache: bool | None = None
    ) -> HttpReply:
        """`use_cache=False` always asks the service (and records nothing), so repeated samples differ;
        None follows the transport's default, which covers search, extraction and embeddings."""
        return await self._send("POST", url, self._post_body(payload), headers, use_cache)

    async def get(self, url: str, params: Mapping[str, str], headers: Mapping[str, str]) -> HttpReply:
        return await self._send("GET", self._full_url(url, params), "", headers, None)

    @staticmethod
    def _post_body(payload: JsonValue) -> str:
        return json.dumps(payload, sort_keys=True)

    @staticmethod
    def _full_url(url: str, params: Mapping[str, str]) -> str:
        return str(httpx.URL(url, params=dict(params)))

    async def post_model[T: BaseModel](
        self, url: str, payload: JsonValue, headers: Mapping[str, str], model: type[T]
    ) -> T:
        reply = await self.post(url, payload, headers)
        return self._validated(reply, model, self._key("POST", url, self._post_body(payload)))

    async def get_model[T: BaseModel](
        self, url: str, params: Mapping[str, str], headers: Mapping[str, str], model: type[T]
    ) -> T:
        reply = await self.get(url, params, headers)
        return self._validated(reply, model, self._key("GET", self._full_url(url, params), ""))

    def _validated[T: BaseModel](self, reply: HttpReply, model: type[T], key: str) -> T:
        """A reply that is not the expected shape is evicted from the cache before the error propagates,
        so a transient bad body is never replayed."""
        try:
            return model.model_validate_json(reply.text)
        except ValidationError:
            self._cache.forget(key)
            raise

    def forget_post(self, url: str, payload: JsonValue) -> None:
        """Drops a cached reply the caller found unusable, so the next identical request asks again."""
        self._cache.forget(self._key("POST", url, self._post_body(payload)))

    @staticmethod
    def _key(method: str, url: str, body: str) -> str:
        return hashlib.sha256(f"{method} {url}\n{body}".encode()).hexdigest()

    async def _send(
        self, method: str, url: str, body: str, headers: Mapping[str, str], use_cache: bool | None
    ) -> HttpReply:
        if not (self._cache_by_default if use_cache is None else use_cache):
            return await self._send_with_retries(method, url, body, headers)
        key = self._key(method, url, body)
        hit = self._cache.lookup(key)
        if hit is not None:
            return hit
        reply = await self._send_with_retries(method, url, body, headers)
        self._cache.store(key, reply)
        return reply

    async def _send_with_retries(
        self, method: str, url: str, body: str, headers: Mapping[str, str]
    ) -> HttpReply:
        limiter = self.limiter(url)
        last_problem = ""
        wait_hint: float | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            async with limiter:
                started = time.perf_counter()
                try:
                    response = await self._client.request(
                        method,
                        url,
                        content=body.encode() if body else None,
                        headers={**headers, "Content-Type": "application/json"},
                    )
                except httpx.TransportError as error:
                    last_problem = f"{type(error).__name__}: {error}"
                    wait_hint = None
                    limiter.throttled(self._wait(attempt, wait_hint))
                else:
                    latency = time.perf_counter() - started
                    if response.is_success:
                        limiter.succeeded()
                        return HttpReply(text=response.text, latency_s=latency, cached=False)
                    if response.status_code not in self.RETRYABLE_STATUS:
                        raise ServiceRejected(url, response.status_code, response.text)
                    last_problem = f"HTTP {response.status_code}"
                    wait_hint = self._retry_after(response)
                    limiter.throttled(self._wait(attempt, wait_hint))
            # No sleep here: `throttled` set a cooldown that the next `async with limiter` waits out,
            # for every caller of this host, not just this request.
        raise ServiceUnavailable(url, last_problem)

    def _wait(self, attempt: int, hint: float | None) -> float:
        """Exponential backoff with jitter, or the server's Retry-After when it gives one. A shared rate
        limit (HTTP 429) needs minutes, not seconds: one run lost 42 of 53 cases to 6 tries capped at 30 s."""
        backoff = self._backoff_s * math.pow(2, attempt) * (0.5 + random.random())
        server = hint * self._backoff_s if hint is not None else 0.0
        return min(self.MAX_WAIT_S, max(backoff, server))

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after", "")
        try:
            return float(value)
        except ValueError:
            return None
