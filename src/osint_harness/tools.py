import html
import re
import time
from abc import ABC, abstractmethod
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Any, ClassVar
from urllib.parse import quote

from pydantic import BaseModel, Field, ValidationError

from osint_harness.investigation.inquiry import Inquiry, ToolName
from osint_harness.investigation.report import Coverage
from osint_harness.investigation.source import Source, SourceTier
from osint_harness.settings import Settings
from osint_harness.transport import ServiceRejected, ServiceUnavailable, Transport


class PageUnreadable(RuntimeError):
    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"the page at {url} could not be read: {reason or 'no reason given'}")


class UnusableArgument(ValueError):
    def __init__(self, tool: ToolName, argument: str, expected: str) -> None:
        super().__init__(f"{tool.value} needs {expected}, got: {argument[:200]}")


def published_on(text: str | None) -> date | None:
    """A publication date from ISO or RFC 2822 text, or None: an unparseable date is no date at all."""
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError):
        return None


class _TavilyHit(BaseModel):
    url: str
    title: str = ""
    content: str = ""
    published_date: str | None = None


class _TavilySearchReply(BaseModel):
    results: list[_TavilyHit]


class _TavilyPage(BaseModel):
    url: str
    raw_content: str = ""


class _TavilyFailure(BaseModel):
    url: str
    error: str = ""


class _TavilyExtractReply(BaseModel):
    results: list[_TavilyPage]
    failed_results: list[_TavilyFailure] = []


class _WikiHit(BaseModel):
    title: str


class _WikiSearch(BaseModel):
    search: list[_WikiHit]


class _WikiSearchReply(BaseModel):
    query: _WikiSearch


class _WikiPage(BaseModel):
    title: str
    extract: str = ""


class _WikiPages(BaseModel):
    pages: list[_WikiPage] = Field(min_length=1)


class _WikiExtractReply(BaseModel):
    query: _WikiPages


class ResearchTool(ABC):
    """One way of looking something up. `covers` names the kinds of record it can actually check, which is
    what the report's coverage section and its registry-claim validator are built from."""

    name: ClassVar[ToolName]
    purpose: ClassVar[str]
    covers: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    async def gather(self, argument: str) -> list[Source]: ...


class TavilySearch(ResearchTool):
    URL: ClassVar[str] = "https://api.tavily.com/search"
    topic: ClassVar[str]

    def __init__(self, transport: Transport, settings: Settings) -> None:
        self._transport = transport
        self._headers = {"Authorization": f"Bearer {settings.tavily_api_key}"}

    async def gather(self, argument: str) -> list[Source]:
        searched = await self._transport.post_model(
            self.URL,
            {"query": argument[:400], "topic": self.topic, "max_results": 6, "search_depth": "basic"},
            self._headers,
            _TavilySearchReply,
        )
        return [
            Source.from_web(hit.url, hit.title, hit.content, published_on(hit.published_date))
            for hit in searched.results
        ]


class WebSearch(TavilySearch):
    name = ToolName.WEB_SEARCH
    purpose = "General web search. Argument: a search query. Returns snippets from several publishers."
    topic = "general"


class NewsSearch(TavilySearch):
    name = ToolName.NEWS_SEARCH
    purpose = (
        "News search (journalism only), with publication dates. Argument: a search query. Best for events, "
        "lawsuits, arrests, and anything that may have changed recently."
    )
    topic = "news"


class PageReader(ResearchTool):
    name = ToolName.READ_PAGE
    purpose = "Fetch the full text of one web page. Argument: an exact URL already seen in search results."
    URL: ClassVar[str] = "https://api.tavily.com/extract"
    URL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"https?://[^\s\"'<>{}\]\[]+")

    def __init__(self, transport: Transport, settings: Settings) -> None:
        self._transport = transport
        self._headers = {"Authorization": f"Bearer {settings.tavily_api_key}"}

    async def gather(self, argument: str) -> list[Source]:
        found = self.URL_PATTERN.search(argument)
        if found is None:
            raise UnusableArgument(self.name, argument, "a URL")
        extracted = await self._transport.post_model(
            self.URL, {"urls": [found.group(0)]}, self._headers, _TavilyExtractReply
        )
        if not extracted.results and extracted.failed_results:
            raise PageUnreadable(extracted.failed_results[0].url, extracted.failed_results[0].error)
        return [Source.from_web(page.url, page.url, page.raw_content) for page in extracted.results]


class Encyclopedia(ResearchTool):
    name = ToolName.ENCYCLOPEDIA
    purpose = "Wikipedia article text. Argument: the name of a company, person, event or topic."
    URL: ClassVar[str] = "https://en.wikipedia.org/w/api.php"
    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": "OsintHarness/0.2 (https://github.com/osint-harness; research benchmark) python-httpx"
    }

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def gather(self, argument: str) -> list[Source]:
        found = await self._transport.get_model(
            self.URL,
            {
                "action": "query",
                "list": "search",
                "srsearch": argument[:250],
                "srlimit": "1",
                "format": "json",
            },
            self.HEADERS,
            _WikiSearchReply,
        )
        hits = found.query.search
        if not hits:
            return []
        article = await self._transport.get_model(
            self.URL,
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": "1",
                "titles": hits[0].title,
                "format": "json",
                "formatversion": "2",
            },
            self.HEADERS,
            _WikiExtractReply,
        )
        page = article.query.pages[0]
        url = f"https://en.wikipedia.org/wiki/{page.title.replace(' ', '_')}"
        return [Source.from_web(url, f"Wikipedia: {page.title}", page.extract)]


class _WikidataSearch(BaseModel):
    search: list[dict[str, Any]] = []


class _WikidataEntities(BaseModel):
    entities: dict[str, dict[str, Any]] = {}


class Wikidata(ResearchTool):
    """Structured identity: the QID that tells namesakes apart, and dates (founded, dissolved, born, died)."""

    name = ToolName.WIKIDATA
    purpose = (
        "Wikidata structured identity. Argument: a name. Returns the matching entities with their QIDs, "
        "descriptions and key dates (inception, dissolution, birth, death); use it to tell namesakes apart."
    )
    covers = frozenset({"structured_identity"})
    URL: ClassVar[str] = "https://www.wikidata.org/w/api.php"
    DATES: ClassVar[dict[str, str]] = {
        "P571": "inception",
        "P576": "dissolved",
        "P569": "born",
        "P570": "died",
    }
    TEXT: ClassVar[dict[str, str]] = {"P1278": "LEI"}

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def gather(self, argument: str) -> list[Source]:
        found = await self._transport.get_model(
            self.URL,
            {
                "action": "wbsearchentities",
                "search": argument[:200],
                "language": "en",
                "limit": "3",
                "format": "json",
            },
            Encyclopedia.HEADERS,
            _WikidataSearch,
        )
        ids = [str(hit["id"]) for hit in found.search if "id" in hit]
        if not ids:
            return []
        entities = await self._transport.get_model(
            self.URL,
            {
                "action": "wbgetentities",
                "ids": "|".join(ids),
                "props": "labels|descriptions|claims",
                "languages": "en",
                "format": "json",
            },
            Encyclopedia.HEADERS,
            _WikidataEntities,
        )
        return [self._source(qid, entities.entities.get(qid, {})) for qid in ids]

    def _source(self, qid: str, entity: dict[str, Any]) -> Source:
        label = entity.get("labels", {}).get("en", {}).get("value", qid)
        description = entity.get("descriptions", {}).get("en", {}).get("value", "")
        facts = [f"{label} ({qid}): {description}"]
        claims: dict[str, list[dict[str, Any]]] = entity.get("claims", {})
        for prop, meaning in {**self.DATES, **self.TEXT}.items():
            for claim in claims.get(prop, [])[:1]:
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value, dict) and "time" in value:
                    facts.append(f"{meaning}: {str(value['time']).lstrip('+')[:10]}")
                elif isinstance(value, str):
                    facts.append(f"{meaning}: {value}")
        return Source.from_web(f"https://www.wikidata.org/wiki/{qid}", f"Wikidata: {label}", ". ".join(facts))


class _GleifReply(BaseModel):
    data: list[dict[str, Any]] = []


class Gleif(ResearchTool):
    name = ToolName.GLEIF
    purpose = (
        "GLEIF legal-entity register. Argument: a company's legal name. Returns LEI, legal name, "
        "jurisdiction, "
        "legal address, entity status (ACTIVE/INACTIVE) and registration status; a primary record."
    )
    covers = frozenset({"legal_entity_identifier"})
    URL: ClassVar[str] = "https://api.gleif.org/api/v1/lei-records"

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def gather(self, argument: str) -> list[Source]:
        reply = await self._transport.get_model(
            self.URL,
            {"filter[fulltext]": argument[:200], "page[size]": "3"},
            {"Accept": "application/vnd.api+json"},
            _GleifReply,
        )
        return [self._source(record) for record in reply.data if record.get("attributes")]

    @staticmethod
    def _source(record: dict[str, Any]) -> Source:
        attributes: dict[str, Any] = record["attributes"]
        entity: dict[str, Any] = attributes.get("entity", {})
        registration: dict[str, Any] = attributes.get("registration", {})
        address: dict[str, Any] = entity.get("legalAddress", {})
        lei = str(attributes.get("lei", record.get("id", "")))
        name = entity.get("legalName", {}).get("name", lei)
        text = (
            f"{name} - LEI {lei}. Jurisdiction: {entity.get('jurisdiction', '?')}. "
            f"Legal address: {address.get('city', '?')}, {address.get('country', '?')}. "
            f"Entity status: {entity.get('status', '?')}. Registration status: "
            f"{registration.get('status', '?')}. "
            f"Registered {str(registration.get('initialRegistrationDate', '?'))[:10]}, last updated "
            f"{str(registration.get('lastUpdateDate', '?'))[:10]}."
        )
        return Source.from_web(
            f"https://search.gleif.org/#/record/{lei}", f"GLEIF: {name}", text, tier=SourceTier.OFFICIAL
        )


class _EdgarReply(BaseModel):
    hits: dict[str, Any] = {}


class SecEdgar(ResearchTool):
    name = ToolName.SEC_EDGAR
    purpose = (
        "SEC EDGAR full-text search of US filings since 2001. Argument: a company or person name, optionally "
        "with a phrase (e.g. 'Nikola bankruptcy'). Returns filings (form, date, filer); a primary record."
    )
    covers = frozenset({"sec_filings"})
    URL: ClassVar[str] = "https://efts.sec.gov/LATEST/search-index"

    def __init__(self, transport: Transport, settings: Settings) -> None:
        self._transport = transport
        self._headers = {"User-Agent": settings.sec_user_agent}

    async def gather(self, argument: str) -> list[Source]:
        reply = await self._transport.get_model(self.URL, {"q": argument[:200]}, self._headers, _EdgarReply)
        hits: list[dict[str, Any]] = reply.hits.get("hits", [])[:6]
        return [source for source in (self._source(hit) for hit in hits) if source is not None]

    @staticmethod
    def _source(hit: dict[str, Any]) -> Source | None:
        found: dict[str, Any] = hit.get("_source", {})
        accession, _, filename = str(hit.get("_id", "")).partition(":")
        ciks: list[str] = found.get("ciks", [])
        if not (accession and filename and ciks):
            return None
        cik = str(int(ciks[0]))
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{filename}"
        filers = "; ".join(found.get("display_names", []))
        text = (
            f"SEC filing {found.get('form', '?')} ({found.get('file_type', '')}) filed "
            f"{found.get('file_date', '?')} "
            f"by {filers}. Period of report: {found.get('period_ending', '?')}. Items: "
            f"{', '.join(found.get('items', []) or []) or 'n/a'}."
        )
        return Source.from_web(
            url,
            f"SEC {found.get('form', 'filing')}: {filers[:80]}",
            text,
            published_on(found.get("file_date")),
        )


class _CourtReply(BaseModel):
    results: list[dict[str, Any]] = []


class CourtRecords(ResearchTool):
    name = ToolName.COURT_RECORDS
    purpose = (
        "US court opinions and RECAP dockets (CourtListener). Argument: a party name, optionally with a "
        "topic. "
        "Returns case names, courts, dates and docket numbers; a primary record."
    )
    covers = frozenset({"court_records"})
    URL: ClassVar[str] = "https://www.courtlistener.com/api/rest/v4/search/"

    def __init__(self, transport: Transport, settings: Settings) -> None:
        self._transport = transport
        token = settings.courtlistener_token
        self._headers = {"Authorization": f"Token {token}"} if token else {}

    async def gather(self, argument: str) -> list[Source]:
        reply = await self._transport.get_model(
            self.URL, {"q": argument[:200], "type": "o", "order_by": "score desc"}, self._headers, _CourtReply
        )
        return [source for source in (self._source(r) for r in reply.results[:6]) if source is not None]

    @staticmethod
    def _source(result: dict[str, Any]) -> Source | None:
        path = result.get("absolute_url")
        if not path:
            return None
        name = result.get("caseName", "case")
        filed = result.get("dateFiled")
        snippet = " ".join(
            str(opinion.get("snippet", ""))
            for opinion in result.get("opinions", [])
            if isinstance(opinion, dict)
        )
        text = (
            f"{name}. Court: {result.get('court', '?')}. Filed {filed or '?'}. Docket "
            f"{result.get('docketNumber', '?')}. "
            f"{html.unescape(re.sub(r'<[^>]+>', '', snippet))}"
        )
        return Source.from_web(
            f"https://www.courtlistener.com{path}", f"CourtListener: {name}", text, published_on(filed)
        )


class _WaybackReply(BaseModel):
    archived_snapshots: dict[str, Any] = {}


class Wayback(ResearchTool):
    name = ToolName.WAYBACK
    purpose = (
        "Internet Archive copy of a page. Argument: an exact URL, optionally followed by a date YYYYMMDD. "
        "Use it for pages that were deleted or changed."
    )
    covers = frozenset({"archived_pages"})
    URL: ClassVar[str] = "https://archive.org/wayback/available"

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def gather(self, argument: str) -> list[Source]:
        found = PageReader.URL_PATTERN.search(argument)
        if found is None:
            raise UnusableArgument(self.name, argument, "a URL")
        when = re.search(r"\b(19|20)\d{6}\b", argument[found.end() :])
        params = {"url": found.group(0)} | ({"timestamp": when.group(0)} if when else {})
        reply = await self._transport.get_model(self.URL, params, {}, _WaybackReply)
        closest: dict[str, Any] = reply.archived_snapshots.get("closest") or {}
        if not closest.get("available") or not closest.get("url"):
            return []
        stamp = str(closest.get("timestamp", ""))
        raw_url = f"https://web.archive.org/web/{stamp}id_/{found.group(0)}"
        page = await self._transport.get(raw_url, {}, Encyclopedia.HEADERS)
        text = html.unescape(
            re.sub(r"\s+", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", page.text, flags=re.S))
        )
        archived = datetime.strptime(stamp[:8], "%Y%m%d").date() if len(stamp) >= 8 else None
        return [
            Source.from_web(str(closest["url"]), f"Archived copy of {found.group(0)}", text.strip(), archived)
        ]


class _SanctionsReply(BaseModel):
    results: list[dict[str, Any]] = []


class Sanctions(ResearchTool):
    name = ToolName.SANCTIONS
    purpose = (
        "OpenSanctions screening across OFAC, EU, UN, UK and other sanctions and PEP lists. Argument: a "
        "person "
        "or company name. Returns matching listed entities, the lists they appear on, and why."
    )
    covers = frozenset({"sanctions", "pep_lists"})
    URL: ClassVar[str] = "https://api.opensanctions.org/search/default"

    def __init__(self, transport: Transport, settings: Settings) -> None:
        self._transport = transport
        self._headers = {"Authorization": f"ApiKey {settings.opensanctions_api_key}"}

    async def gather(self, argument: str) -> list[Source]:
        reply = await self._transport.get_model(
            self.URL, {"q": argument[:200], "limit": "5"}, self._headers, _SanctionsReply
        )
        return [self._source(result) for result in reply.results if result.get("id")]

    @staticmethod
    def _source(result: dict[str, Any]) -> Source:
        properties: dict[str, list[str]] = result.get("properties", {})
        name = result.get("caption", result["id"])
        text = (
            f"{name} ({result.get('schema', '?')}). Lists: {', '.join(result.get('datasets', []))}. "
            f"Topics: {', '.join(properties.get('topics', [])) or 'none'}. "
            f"Country: {', '.join(properties.get('country', [])) or '?'}. "
            f"Reason: {' '.join(properties.get('notes', [])[:2]) or 'not stated'}"
        )
        return Source.from_web(
            f"https://www.opensanctions.org/entities/{quote(str(result['id']))}/",
            f"OpenSanctions: {name}",
            text,
            tier=SourceTier.OFFICIAL,
        )


class Toolbox:
    """The research tools an investigator may choose between; a failing service is reported, not fatal."""

    def __init__(self, tools: list[ResearchTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    @classmethod
    def standard(cls, transport: Transport, settings: Settings) -> "Toolbox":
        tools: list[ResearchTool] = [
            WebSearch(transport, settings),
            NewsSearch(transport, settings),
            PageReader(transport, settings),
            Encyclopedia(transport),
            Wikidata(transport),
            Gleif(transport),
            SecEdgar(transport, settings),
            CourtRecords(transport, settings),
            Wayback(transport),
        ]
        if settings.opensanctions_api_key:
            tools.append(Sanctions(transport, settings))
        return cls(tools)

    @property
    def catalogue(self) -> str:
        return "\n".join(f"- {tool.name.value}: {tool.purpose}" for tool in self._tools.values())

    def offers(self, tool: ToolName) -> bool:
        return tool in self._tools

    def coverage(self, called: set[ToolName]) -> Coverage:
        return Coverage(
            {name.value: tool.covers for name, tool in self._tools.items()},
            frozenset(name.value for name in called),
        )

    async def use(self, tool: ToolName, argument: str, question_id: str, step: int) -> Inquiry:
        """Service errors, unparseable replies and unusable arguments become a failed inquiry, not a crash."""
        started = time.perf_counter()
        try:
            if not argument.strip():
                raise UnusableArgument(tool, argument, "a non-empty argument")
            if tool not in self._tools:
                raise UnusableArgument(tool, argument, "a tool this toolbox offers")
            sources = await self._tools[tool].gather(argument)
        except (
            ServiceRejected,
            ServiceUnavailable,
            UnusableArgument,
            PageUnreadable,
            ValidationError,
        ) as error:
            failure = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            return Inquiry(tool, argument, question_id, step, (), time.perf_counter() - started, failure)
        kept = tuple(source for source in sources if source.content.strip())
        return Inquiry(tool, argument, question_id, step, kept, time.perf_counter() - started)
