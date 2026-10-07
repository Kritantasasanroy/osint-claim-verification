import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class MissingSetting(RuntimeError):
    def __init__(self, name: str) -> None:
        super().__init__(f"{name} is not set. Copy .env.example to .env and fill it in, or export it.")


@dataclass(frozen=True)
class TokenPrice:
    input_per_mtok: float
    output_per_mtok: float


@dataclass(frozen=True)
class Settings:
    nvidia_api_key: str
    tavily_api_key: str
    llm_model: str
    ocr_model: str
    embedding_model: str
    llm_reasoning: bool
    max_concurrent_requests: int
    price: TokenPrice
    cache_path: Path
    judge_model: str = "z-ai/glm-5.3-flash"
    temperature: float = 0.2
    llm_cache: bool = True
    search_cache: bool = True
    sec_user_agent: str = "OsintHarness/0.2 research-benchmark (contact: set SEC_USER_AGENT)"
    courtlistener_token: str = ""
    opensanctions_api_key: str = ""

    def public(self) -> dict[str, str | float | bool | int]:
        """Everything that shapes a run except the secrets, for the run manifest."""
        return {
            "llm_model": self.llm_model,
            "judge_model": self.judge_model,
            "ocr_model": self.ocr_model,
            "embedding_model": self.embedding_model,
            "llm_reasoning": self.llm_reasoning,
            "temperature": self.temperature,
            "llm_cache": self.llm_cache,
            "search_cache": self.search_cache,
            "max_concurrent_requests": self.max_concurrent_requests,
            "price_input_per_mtok": self.price.input_per_mtok,
            "price_output_per_mtok": self.price.output_per_mtok,
        }

    @classmethod
    def from_environment(cls, env_file: Path = Path(".env")) -> "Settings":
        load_dotenv(env_file)
        return cls(
            nvidia_api_key=cls._required("NVIDIA_API_KEY"),
            tavily_api_key=cls._required("TAVILY_API_KEY"),
            llm_model=os.environ.get("LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            ocr_model=os.environ.get("OCR_MODEL", "nvidia/nemotron-parse"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b"),
            llm_reasoning=os.environ.get("LLM_REASONING", "true").lower() == "true",
            max_concurrent_requests=int(os.environ.get("MAX_CONCURRENT_REQUESTS", "4")),
            price=TokenPrice(
                input_per_mtok=float(os.environ.get("PRICE_INPUT_PER_MTOK", "0.10")),
                output_per_mtok=float(os.environ.get("PRICE_OUTPUT_PER_MTOK", "0.50")),
            ),
            cache_path=Path(os.environ.get("CACHE_PATH", ".cache/responses.sqlite3")),
            # A judge from another model family, so the grader does not share the agent's blind spots (E5).
            judge_model=os.environ.get("JUDGE_MODEL", "z-ai/glm-5.3-flash"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.2")),
            sec_user_agent=os.environ.get(
                "SEC_USER_AGENT", "OsintHarness/0.2 research-benchmark (contact: set SEC_USER_AGENT)"
            ),
            courtlistener_token=os.environ.get("COURTLISTENER_TOKEN", "").strip(),
            opensanctions_api_key=os.environ.get("OPENSANCTIONS_API_KEY", "").strip(),
        )

    @staticmethod
    def _required(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise MissingSetting(name)
        return value
