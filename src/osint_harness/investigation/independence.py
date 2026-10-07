import re
from dataclasses import dataclass
from typing import ClassVar

from osint_harness.investigation.inquiry import Inquiry, ToolName
from osint_harness.investigation.source import Source


class PublisherClusters:
    """Groups sources that are really one publication: the same domain, or near-identical text on several
    domains (a wire story, a press release, a mirror). Independence is counted per cluster, not per domain.
    """

    SHINGLE: ClassVar[int] = 5
    SAME_TEXT: ClassVar[float] = 0.6
    MIN_SHINGLES: ClassVar[int] = 8

    def __init__(self, sources: list[Source]) -> None:
        self._label: dict[str, str] = {}
        parent: dict[str, str] = {}

        def root(key: str) -> str:
            while parent[key] != key:
                parent[key] = parent[parent[key]]
                key = parent[key]
            return key

        def join(a: str, b: str) -> None:
            parent[root(b)] = root(a)

        shingles = {source.url: self.shingles(source.content) for source in sources}
        first_of_domain: dict[str, str] = {}
        for source in sources:
            parent[source.url] = source.url
            if source.domain in first_of_domain:
                join(first_of_domain[source.domain], source.url)
            else:
                first_of_domain[source.domain] = source.url
        for i, a in enumerate(sources):
            for b in sources[i + 1 :]:
                if self.similarity(shingles[a.url], shingles[b.url]) >= self.SAME_TEXT:
                    join(a.url, b.url)
        domain_of = {source.url: source.domain for source in sources}
        self._label = {url: domain_of[root(url)] for url in parent}

    def of(self, url: str, fallback: str) -> str:
        return self._label.get(url, fallback)

    @classmethod
    def shingles(cls, text: str) -> frozenset[str]:
        words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
        return frozenset(" ".join(words[i : i + cls.SHINGLE]) for i in range(len(words) - cls.SHINGLE + 1))

    @classmethod
    def similarity(cls, a: frozenset[str], b: frozenset[str]) -> float:
        if len(a) < cls.MIN_SHINGLES or len(b) < cls.MIN_SHINGLES:
            return 0.0
        return len(a & b) / len(a | b)


@dataclass(frozen=True)
class Repeat:
    tool: ToolName
    argument: str
    earlier: str


class QueryLedger:
    """Every query an investigation has issued. A controller rule, not agent memory: it applies in every
    memory mode, because re-issuing a query is waste whether or not the agent remembers having asked it."""

    SAME_QUERY: ClassVar[float] = 0.8
    SEARCHES: ClassVar[frozenset[ToolName]] = frozenset(
        {ToolName.WEB_SEARCH, ToolName.NEWS_SEARCH, ToolName.ENCYCLOPEDIA}
    )

    def __init__(self, inquiries: list[Inquiry]) -> None:
        self._issued = [(inquiry.tool, inquiry.argument) for inquiry in inquiries]

    def repeat_of(self, tool: ToolName, argument: str) -> Repeat | None:
        tokens = self.tokens(argument)
        for earlier_tool, earlier in self._issued:
            if tool in self.SEARCHES and earlier_tool in self.SEARCHES:
                if self.jaccard(tokens, self.tokens(earlier)) >= self.SAME_QUERY:
                    return Repeat(tool, argument, earlier)
            elif tool is earlier_tool and argument.strip().lower() == earlier.strip().lower():
                return Repeat(tool, argument, earlier)
        return None

    def admit(self, tool: ToolName, argument: str) -> Repeat | None:
        """Records the query unless it repeats an earlier one, in which case the repeat is returned."""
        repeat = self.repeat_of(tool, argument)
        if repeat is None:
            self._issued.append((tool, argument))
        return repeat

    @staticmethod
    def tokens(query: str) -> frozenset[str]:
        return frozenset(re.sub(r"[^a-z0-9]+", " ", query.lower()).split())

    @staticmethod
    def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
        return len(a & b) / len(a | b) if a | b else 1.0
