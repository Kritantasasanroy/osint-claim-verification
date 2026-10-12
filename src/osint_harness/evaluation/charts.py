from collections.abc import Callable
from pathlib import Path
from statistics import fmean
from typing import ClassVar

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from osint_harness.evaluation.scoreboard import ModeSummary, Scoreboard
from osint_harness.evaluation.stats import Estimate
from osint_harness.investigation.case_file import MemoryMode


class BenchmarkCharts:
    """Static PNG charts of a benchmark run; one fixed colour per memory mode across every chart."""

    MODE_COLOURS: ClassVar[dict[MemoryMode, str]] = {
        MemoryMode.CLOSED_BOOK: "#8a8984",
        MemoryMode.LONG_ONLY: "#9b59b6",
        MemoryMode.NONE: "#2a78d6",
        MemoryMode.SHORT: "#eb6834",
        MemoryMode.LONG: "#1baf7a",
    }
    SURFACE: ClassVar[str] = "#fcfcfb"
    INK: ClassVar[str] = "#0b0b0b"
    MUTED: ClassVar[str] = "#52514e"
    GRID: ClassVar[str] = "#e4e3df"
    ROLLING_WINDOW: ClassVar[int] = 5

    def __init__(self, scoreboard: Scoreboard) -> None:
        self._scoreboard = scoreboard
        self._summaries = [scoreboard.summary(mode) for mode in scoreboard.modes]

    def draw(self, folder: Path) -> list[Path]:
        folder.mkdir(parents=True, exist_ok=True)
        return [
            self._by_step(
                folder / "reward_progression.png",
                "Mean step reward by research round",
                "step reward",
                lambda s: s.step_reward_by_step,
            ),
            self._by_step(
                folder / "confidence_convergence.png",
                "Probability on an acceptable verdict, by research round",
                "P(acceptable verdict)",
                lambda s: s.p_correct_by_step,
            ),
            self._memory_comparison(folder / "memory_comparison.png"),
            self._efficiency(folder / "efficiency.png"),
            self._frontier(folder / "accuracy_vs_tokens.png"),
            self._failure_modes(folder / "failure_modes.png"),
            self._learning_curve(folder / "learning_curve.png"),
        ]

    def _figure(self, width: float, height: float, columns: int = 1) -> tuple[Figure, list[Axes]]:
        figure = Figure(figsize=(width, height), dpi=150, facecolor=self.SURFACE)
        axes = [figure.add_subplot(1, columns, i + 1) for i in range(columns)]
        for axis in axes:
            axis.set_facecolor(self.SURFACE)
            axis.grid(True, color=self.GRID, linewidth=0.8)
            axis.set_axisbelow(True)
            for side in ("top", "right"):
                axis.spines[side].set_visible(False)
            for side in ("left", "bottom"):
                axis.spines[side].set_color(self.MUTED)
            axis.tick_params(colors=self.MUTED, labelsize=8)
        return figure, axes

    def _title(self, axis: Axes, title: str, ylabel: str = "", xlabel: str = "") -> None:
        axis.set_title(title, color=self.INK, fontsize=10, loc="left")
        axis.set_ylabel(ylabel, color=self.MUTED, fontsize=8)
        axis.set_xlabel(xlabel, color=self.MUTED, fontsize=8)

    def _save(self, figure: Figure, path: Path) -> Path:
        figure.tight_layout()
        figure.savefig(path, facecolor=self.SURFACE)
        return path

    def _legend(self, axis: Axes) -> None:
        axis.legend(frameon=False, fontsize=8, labelcolor=self.INK)

    def _by_step(
        self, path: Path, title: str, ylabel: str, series: Callable[[ModeSummary], list[float]]
    ) -> Path:
        figure, [axis] = self._figure(6.5, 3.6)
        for summary in self._summaries:
            values = series(summary)
            steps = list(range(1, len(values) + 1))
            colour = self.MODE_COLOURS[summary.mode]
            axis.plot(
                steps, values, color=colour, linewidth=2, marker="o", markersize=5, label=summary.mode.value
            )
            if values:
                axis.annotate(
                    f"{values[-1]:.2f}",
                    (steps[-1], values[-1]),
                    textcoords="offset points",
                    xytext=(6, 0),
                    fontsize=7,
                    color=self.INK,
                    va="center",
                )
        axis.set_xticks(range(1, max((len(series(s)) for s in self._summaries), default=1) + 1))
        self._title(axis, title, ylabel, "research round")
        self._legend(axis)
        return self._save(figure, path)

    def _memory_comparison(self, path: Path) -> Path:
        """Bars with 95% bootstrap intervals where the metric has one."""
        panels: list[tuple[str, Callable[[ModeSummary], float | Estimate]]] = [
            ("Accuracy (95% CI)", lambda s: s.accuracy),
            ("Episode reward (95% CI)", lambda s: s.episode_reward),
            ("Calibration error (ECE, lower is better)", lambda s: s.shipped.ece),
            ("Misleading memory rate", lambda s: s.memory_misleading_rate),
        ]
        figure, axes = self._figure(14, 3.4, columns=len(panels))
        for axis, (title, metric) in zip(axes, panels, strict=True):
            names = [s.mode.value for s in self._summaries]
            measured = [metric(s) for s in self._summaries]
            values = [m.mean if isinstance(m, Estimate) else m for m in measured]
            errors = [
                [m.mean - m.low if isinstance(m, Estimate) else 0.0 for m in measured],
                [m.high - m.mean if isinstance(m, Estimate) else 0.0 for m in measured],
            ]
            bars = axis.bar(
                names,
                values,
                yerr=errors,
                ecolor=self.INK,
                capsize=3,
                color=[self.MODE_COLOURS[s.mode] for s in self._summaries],
                width=0.6,
                edgecolor=self.SURFACE,
                linewidth=2,
            )
            axis.bar_label(bars, labels=[f"{v:.2f}" for v in values], fontsize=8, color=self.INK, padding=2)
            axis.set_ylim(0, max([*values, 0.0]) * 1.25 or 1.0)
            axis.tick_params(axis="x", labelrotation=20)
            self._title(axis, title)
        return self._save(figure, path)

    def _efficiency(self, path: Path) -> Path:
        figure, [axis] = self._figure(6.5, 3.8)
        for mode in self._scoreboard.modes:
            runs = self._scoreboard.by_mode(mode)
            axis.scatter(
                [(r.prompt_tokens + r.completion_tokens) / 1000 for r in runs],
                [r.episode_reward.total for r in runs],
                s=28,
                color=self.MODE_COLOURS[mode],
                edgecolors=self.SURFACE,
                linewidths=1.5,
                label=mode.value,
                alpha=0.9,
            )
        self._title(
            axis,
            "Investigation quality vs token cost (one dot per episode)",
            "episode reward",
            "tokens (thousands)",
        )
        self._legend(axis)
        return self._save(figure, path)

    def _frontier(self, path: Path) -> Path:
        """Accuracy against mean tokens per mode, with both 95% intervals; the closed-book point is the "
        "floor."""
        figure, [axis] = self._figure(6.5, 3.8)
        for summary in self._summaries:
            accuracy, tokens = summary.accuracy, summary.tokens
            axis.errorbar(
                tokens.mean / 1000,
                accuracy.mean,
                xerr=[[(tokens.mean - tokens.low) / 1000], [(tokens.high - tokens.mean) / 1000]],
                yerr=[[accuracy.mean - accuracy.low], [accuracy.high - accuracy.mean]],
                fmt="o",
                color=self.MODE_COLOURS[summary.mode],
                capsize=3,
                label=summary.mode.value,
            )
        axis.set_xscale("symlog", linthresh=1)
        self._title(axis, "Accuracy vs token cost, per mode (95% CI)", "accuracy", "mean tokens (thousands)")
        self._legend(axis)
        return self._save(figure, path)

    def _failure_modes(self, path: Path) -> Path:
        modes = sorted({m for s in self._summaries for m in s.failure_modes}, key=lambda m: m.value)
        figure, [axis] = self._figure(7.5, max(2.5, 0.45 * len(modes) + 1.2))
        height = 0.8 / max(len(self._summaries), 1)
        for index, summary in enumerate(self._summaries):
            positions = [row + index * height for row in range(len(modes))]
            counts = [summary.failure_modes.get(mode, 0) for mode in modes]
            axis.barh(
                positions,
                counts,
                height=height,
                color=self.MODE_COLOURS[summary.mode],
                edgecolor=self.SURFACE,
                linewidth=1,
                label=summary.mode.value,
            )
        axis.set_yticks(
            [row + 0.4 - height / 2 for row in range(len(modes))],
            [mode.value.replace("_", " ") for mode in modes],
        )
        axis.invert_yaxis()
        self._title(axis, "Failure modes across episodes (an episode can show several)", "", "episodes")
        axis.xaxis.set_major_locator(MaxNLocator(integer=True))
        axis.legend(
            frameon=False, fontsize=8, labelcolor=self.INK, loc="upper left", bbox_to_anchor=(1.0, 1.0)
        )
        return self._save(figure, path)

    def _learning_curve(self, path: Path) -> Path:
        figure, [axis] = self._figure(6.5, 3.6)
        for summary in self._summaries:
            rewards = summary.episode_reward_in_order
            window = self.ROLLING_WINDOW
            rolling = [fmean(rewards[max(0, i - window + 1) : i + 1]) for i in range(len(rewards))]
            axis.plot(
                range(1, len(rolling) + 1),
                rolling,
                color=self.MODE_COLOURS[summary.mode],
                linewidth=2,
                label=summary.mode.value,
            )
        self._title(
            axis,
            f"Episode reward over the case sequence (rolling mean of {self.ROLLING_WINDOW})",
            "episode reward",
            "case number (benchmark order)",
        )
        self._legend(axis)
        return self._save(figure, path)
