import json
from collections.abc import Callable
from typing import ClassVar

import httpx

from osint_harness.harness import Harness
from osint_harness.investigation.confidence import ConfidenceCalibrator
from osint_harness.settings import Settings
from osint_harness.transport import Transport

type Handler = Callable[[httpx.Request], httpx.Response]


class FakeServices:
    """Stands in for the NVIDIA and Tavily HTTP APIs; answers each agent by the schema it asks for."""

    REUTERS: ClassVar[str] = "https://www.reuters.com/wirecard-ey"
    FT: ClassVar[str] = "https://www.ft.com/wirecard-audit"
    EMBEDDING_TOKENS: ClassVar[int] = 7
    QUOTE: ClassVar[str] = "EY audited Wirecard for a decade"

    def __init__(self, publishers: list[str]) -> None:
        self.publishers = publishers
        self.prompts: dict[str, list[str]] = {}
        self.systems: dict[str, list[str]] = {}
        self.models: dict[str, list[str]] = {}
        self.items_demanded: dict[str, dict[str, int]] = {}
        self.cheap_check: dict[str, str] | None = None

    def harness(self, settings: Settings, make_transport: Callable[[Handler], Transport]) -> Harness:
        return Harness(settings, make_transport(self.handle), ConfidenceCalibrator())

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.tavily.com" and request.method == "GET":
            return httpx.Response(200, json={})
        body = json.loads(request.content)
        if request.url.host == "api.tavily.com":
            return httpx.Response(200, json={"results": [self.search_hit(url) for url in self.publishers]})
        if request.url.path.endswith("/embeddings"):
            vectors = [[1.0, float("wirecard" in text.lower())] for text in body["input"]]
            return httpx.Response(
                200,
                json={
                    "data": [{"embedding": v} for v in vectors],
                    "usage": {"prompt_tokens": self.EMBEDDING_TOKENS, "completion_tokens": 0},
                },
            )
        schema = body["response_format"]["json_schema"]
        self.prompts.setdefault(schema["name"], []).append(body["messages"][1]["content"])
        self.systems.setdefault(schema["name"], []).append(body["messages"][0]["content"])
        self.models.setdefault(schema["name"], []).append(body["model"])
        self.items_demanded[schema["name"]] = {
            field: spec.get("minItems", 0) for field, spec in schema["schema"]["properties"].items()
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(self.answer(schema["name"]))}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    @classmethod
    def search_hit(cls, url: str) -> dict[str, str]:
        return {
            "url": url,
            "title": "Wirecard audit",
            "content": f"{cls.QUOTE}.",
            "published_date": "2020-06-25",
        }

    def answer(self, schema: str) -> dict[str, object]:
        if schema == "Grading":
            demanded = self.items_demanded[schema]
            return {
                "key_facts_established": [True, False][: demanded["key_facts_established"]]
                or [True] * demanded["key_facts_established"],
                "findings": [{"atomic_facts": [{"fact": "EY audited Wirecard", "supported": True}]}]
                * demanded["findings"],
                "memory_labels_in_order": ["relevant"] * demanded["memory_labels_in_order"],
            }
        if schema.endswith("Assessment"):
            return self.assessment()
        if schema.endswith("ClosedBookAnswer"):
            return {"reasoning": "EY was Wirecard's auditor.", "verdict": "TRUE", "confidence": 0.9}
        return {
            "Scope": {
                "kind": "claim",
                "entity_name": "Wirecard",
                "disambiguators": [],
                "assertion": "Wirecard was audited by EY",
                "statement": "Wirecard was audited by EY",
            },
            "Plan": {
                "questions": [
                    {"text": "Who audited Wirecard?", "role": "verdict_deciding"},
                    {"text": "When?", "role": "core_fact"},
                ]
            },
            "ResearchAgenda": {
                "actions": [{"tool": "news_search", "argument": "Wirecard auditor", "question_id": "Q1"}]
            },
            "ClaimReflection": self.reflection(),
            "Challenge": {
                "runner_up_case": "A single auditor name could be outdated after a change of auditor.",
                "would_flip_it": ["A filing naming another auditor"],
                "cheap_check": self.cheap_check,
            },
            "ReportDraft": {
                "summary": "EY audited Wirecard.",
                "findings": [
                    {
                        "statement": "EY audited Wirecard",
                        "citation_urls": [self.publishers[0], "https://invented.example/x"],
                    }
                ],
                "conflicts": [],
                "gaps": [],
                "next_steps": [],
                "document_assessment": [],
                "facts_to_remember": [
                    {
                        "relation": "auditor",
                        "value": "EY",
                        "valid_from": None,
                        "statement": "Wirecard's auditor was EY",
                        "confidence": 0.9,
                        "citation_urls": [self.publishers[0]],
                    }
                ],
                "lessons": [
                    {
                        "subject_type": "listed company",
                        "action": "check the auditor in sec_edgar filings first",
                    }
                ],
            },
        }[schema]

    def assessment(self) -> dict[str, object]:
        return {
            "evidence": [
                {
                    "source_number": n,
                    "question_id": "Q1",
                    "statement": "EY was the auditor",
                    "quote": self.QUOTE,
                    "stance": "supports",
                    "strength": "direct",
                    "points_to": "TRUE",
                    "severity": None,
                }
                for n in range(1, len(self.publishers) + 1)
            ]
        }

    def reflection(self) -> dict[str, object]:
        return {
            "critique": "Two independent major publishers agree that EY audited Wirecard; no conflicts.",
            "verdict": "TRUE",
            "verdict_scores": [
                {"verdict": "TRUE", "probability": 0.9},
                {"verdict": "FALSE", "probability": 0.1},
            ],
            "answered_question_ids": ["Q1"],
            "dropped_question_ids": [],
            "follow_up_questions": [],
            "distrusted_memory_ids": [],
            "decision": "conclude",
        }
