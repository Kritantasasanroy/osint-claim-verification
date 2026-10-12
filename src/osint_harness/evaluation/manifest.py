import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel


class StaleRunDirectory(RuntimeError):
    def __init__(self, run_dir: Path, recorded: str, current: str) -> None:
        super().__init__(
            f"{run_dir} holds results from code {recorded[:12]}, but this is {current[:12]}. Resuming would "
            f"mix "
            "two code versions in one set of numbers: use a new --run-dir, or pass --force-new to start over."
        )


class RunManifest(BaseModel):
    """What produced a run directory, so every number in it can be traced to one code version (H2)."""

    git_sha: str
    dirty: bool
    settings: dict[str, str | float | bool | int]
    budget: dict[str, int]
    benchmark_file: str
    benchmark_sha256: str
    split: str
    seeds: list[int]
    modes: list[str]
    pre_scoped: bool
    started_at: str
    finished_at: str | None = None

    @staticmethod
    def code_version(repo: Path = Path(".")) -> tuple[str, bool]:
        try:
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
            ).stdout.strip()
            status = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return "unknown", True
        return sha, bool(status.strip())

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    @classmethod
    def path_in(cls, run_dir: Path) -> Path:
        return run_dir / "run_manifest.json"

    def open_in(self, run_dir: Path, force_new: bool) -> None:
        """Refuses to resume a run directory written by other code (or another benchmark file)."""
        path = self.path_in(run_dir)
        if path.exists() and not force_new:
            recorded = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
            if (recorded.git_sha, recorded.benchmark_sha256) != (self.git_sha, self.benchmark_sha256):
                raise StaleRunDirectory(run_dir, recorded.git_sha, self.git_sha)
        run_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def close_in(self, run_dir: Path) -> None:
        finished = self.model_copy(update={"finished_at": self.now()})
        self.path_in(run_dir).write_text(finished.model_dump_json(indent=2), encoding="utf-8")
