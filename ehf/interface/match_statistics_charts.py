"""Geometry and display values for the Statistics tab of the match card (SVG user units = px)."""

from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.match_statistics import MatchStatistics, PlayerStats, SaveMark
from ehf.domain.match_summary import REGULATION, SIDES, ComparisonRow, MatchSummary, clock

WIN_WIDTH = 960.0
WIN_LEFT = 52.0
WIN_RIGHT = 22.0
WIN_TOP = 22.0
WIN_PLOT = 190.0
WIN_HEIGHT = WIN_TOP + WIN_PLOT + 30.0

EVENT_KINDS = {
    "goal": "Goal",
    "shot": "Shot without goal",
    "assist": "Assist",
    "save": "Save",
    "conceded": "Goal conceded",
    "turnover": "Turnover",
    "steal": "Steal",
    "block": "Block",
    "seven_won": "7m won",
    "suspension": "2 min",
    "yellow": "Yellow card",
    "red": "Red card",
}


@dataclass(frozen=True)
class Tick:
    pos: float
    label: str


@dataclass(frozen=True)
class MomentMark:
    number: int
    x: float
    y: float
    side: str
    clock: str
    who: str
    score: str
    before: str
    after: str


@dataclass(frozen=True)
class WinChart:
    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float
    mid: float
    line: str
    area: str
    x_ticks: tuple[Tick, ...]
    y_ticks: tuple[Tick, ...]
    half_x: float
    moments: tuple[MomentMark, ...]


def win_chart(summary: MatchSummary) -> WinChart:
    end = summary.flow.end_seconds
    plot_w = WIN_WIDTH - WIN_LEFT - WIN_RIGHT

    def x(seconds: float) -> float:
        return WIN_LEFT + plot_w * min(max(seconds, 0), end) / end

    def y(probability: float) -> float:
        return WIN_TOP + WIN_PLOT * (1 - probability)

    points = summary.win.points
    line = "M" + " L".join(f"{x(t):.1f},{y(p):.1f}" for t, p in points)
    mid = y(0.5)
    area = f"M{x(points[0][0]):.1f},{mid:.1f} L" + line[1:] + f" L{x(points[-1][0]):.1f},{mid:.1f} Z"
    minutes = list(range(0, end // 60 + 1, 10))
    moments = []
    for number, moment in enumerate(summary.win.moments, start=1):
        moments.append(
            MomentMark(
                number=number,
                x=x(moment.seconds),
                y=y(moment.after),
                side=moment.side,
                clock=clock(moment.seconds),
                who=moment.scorer.label if moment.scorer else "",
                score=f"{moment.home}:{moment.away}",
                before=f"{moment.before:.0%}",
                after=f"{moment.after:.0%}",
            )
        )
    return WinChart(
        width=WIN_WIDTH,
        height=WIN_HEIGHT,
        left=WIN_LEFT,
        right=WIN_WIDTH - WIN_RIGHT,
        top=WIN_TOP,
        bottom=WIN_TOP + WIN_PLOT,
        mid=mid,
        line=line,
        area=area,
        x_ticks=tuple(Tick(x(m * 60), f"{m}'") for m in minutes),
        y_ticks=tuple(Tick(y(p / 100), f"{p}%") for p in (0, 25, 50, 75, 100)),
        half_x=x(REGULATION / 2),
        moments=tuple(moments),
    )


@dataclass(frozen=True)
class Dot:
    left: float
    kind: str
    title: str


def player_dots(player: PlayerStats, end: int) -> tuple[Dot, ...]:
    """Positions (0–100 %) of a player's events on a strip covering the match."""
    return tuple(
        Dot(
            left=min(100.0, 100.0 * event.seconds / end),
            kind=event.kind,
            title=f"{event.clock} · {event.score} · {event.title}" + (f" · {event.detail}" if event.detail else ""),
        )
        for event in player.events
    )


def save_dots(marks: tuple[SaveMark, ...], end: int) -> tuple[Dot, ...]:
    return tuple(
        Dot(
            left=min(100.0, 100.0 * mark.seconds / end),
            kind="save" if mark.saved else "conceded",
            title=f"{clock(mark.seconds)} · {'save' if mark.saved else 'goal conceded'}{' · 7m' if mark.seven else ''}",
        )
        for mark in marks
    )


def bar_width(row: ComparisonRow, side: str) -> float:
    value = row.home if side == "home" else row.away
    return round(100 * value / row.scale, 1) if row.scale else 0.0


def average_left(row: ComparisonRow) -> float | None:
    return round(100 * row.average / row.scale, 1) if row.average is not None and row.scale else None


@dataclass(frozen=True)
class Kpi:
    label: str
    home: str
    away: str
    better: str | None
    note: str
    home_sub: str = ""
    away_sub: str = ""


def kpis(stats: MatchStatistics) -> tuple[Kpi, ...]:
    summary = stats.summary
    home, away = summary.figures["home"], summary.figures["away"]
    shoot = stats.shooting
    base = summary.baseline.values if summary.baseline else {}

    def pct(value: float | None) -> str:
        return f"{value:.0%}" if value is not None else "–"

    def better(h: float | None, a: float | None, higher: bool = True) -> str | None:
        if h is None or a is None or h == a:
            return None
        return "home" if (h > a) == higher else "away"

    items = [
        Kpi(
            "Goals vs expected (xG)",
            str(shoot["home"].goals),
            str(shoot["away"].goals),
            better(shoot["home"].goals_above_expected, shoot["away"].goals_above_expected),
            "expected goals from the same shots",
            home_sub=f"xG {shoot['home'].xg:.1f}",
            away_sub=f"xG {shoot['away'].xg:.1f}",
        ),
        Kpi(
            "Shooting",
            pct(home.shooting),
            pct(away.shooting),
            better(home.shooting, away.shooting),
            f"Ø {pct(base.get('shooting'))}" if base.get("shooting") else "goals / shots",
        ),
        Kpi(
            "Goalkeeper saves",
            pct(home.saving),
            pct(away.saving),
            better(home.saving, away.saving),
            f"Ø {pct(base.get('saving'))}" if base.get("saving") else "saves / shots on target",
        ),
    ]
    if home.attack is not None and away.attack is not None:
        items.append(
            Kpi(
                "Attack efficiency",
                pct(home.attack),
                pct(away.attack),
                better(home.attack, away.attack),
                f"Ø {pct(base.get('attack'))}" if base.get("attack") else "goals / (shots + turnovers)",
            )
        )
        items.append(
            Kpi(
                "Attacks (est.)",
                str(shoot["home"].possessions),
                str(shoot["away"].possessions),
                None,
                "shots + turnovers",
            )
        )
    return tuple(items)


# ---------------------------------------------------------------------- goalkeeper charts

GK_WIDTH = 460.0
GK_LEFT = 42.0
GK_RIGHT = 28.0
GK_TOP = 22.0
GK_PLOT = 150.0
GK_HEIGHT = GK_TOP + GK_PLOT + 30.0


@dataclass(frozen=True)
class PeriodBar:
    label: str
    x: float
    y: float
    width: float
    height: float
    rate: float | None
    saves: int
    faced: int
    empty: bool


@dataclass(frozen=True)
class KeeperPeriodChart:
    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float
    bars: tuple[PeriodBar, ...]
    y_ticks: tuple[Tick, ...]
    avg_y: float | None
    side: str


@dataclass(frozen=True)
class GsaaMomentumChart:
    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float
    zero_y: float
    line: str
    area: str
    x_ticks: tuple[Tick, ...]
    y_ticks: tuple[Tick, ...]
    half_x: float
    end_value: float
    end_pos: tuple[float, float]
    side: str


@dataclass(frozen=True)
class DuelRow:
    number: str
    name: str
    faced: int
    saves: int

    @property
    def rate(self) -> float | None:
        return self.saves / self.faced if self.faced else None

    @property
    def heat(self) -> float:
        return self.rate if self.rate is not None else 0.0


@dataclass(frozen=True)
class KeeperSideCharts:
    side: str
    periods: KeeperPeriodChart
    momentum: GsaaMomentumChart
    duels: tuple[DuelRow, ...]


def keeper_charts(stats: MatchStatistics, competition_save: float | None = None) -> dict[str, KeeperSideCharts]:
    end = stats.end_seconds
    return {
        side: KeeperSideCharts(
            side=side,
            periods=_period_chart(stats.team_save_marks(side), end, side, competition_save),
            momentum=_gsaa_momentum(stats.team_save_marks(side), end, side),
            duels=_duel_rows(stats.team_save_marks(side)),
        )
        for side in SIDES
        if stats.save_marks[side]
    }


def _period_labels(end: int) -> tuple[tuple[str, int, int], ...]:
    buckets = [(f"{start}'", start * 60, (start + 10) * 60) for start in range(0, 60, 10)]
    if end > REGULATION:
        buckets.append(("ET", REGULATION, end))
    return tuple(buckets)


def _period_chart(
    marks: tuple[SaveMark, ...], end: int, side: str, competition_save: float | None
) -> KeeperPeriodChart:
    plot_w = GK_WIDTH - GK_LEFT - GK_RIGHT
    buckets = _period_labels(end)
    slot = plot_w / len(buckets)
    bar_w = slot * 0.55
    bottom = GK_TOP + GK_PLOT

    bars = []
    for index, (label, start, stop) in enumerate(buckets):
        faced = [m for m in marks if start < m.seconds <= stop]
        saves = sum(1 for m in faced if m.saved)
        count = len(faced)
        rate = saves / count if count else None
        height = GK_PLOT * (rate or 0)
        centre = GK_LEFT + slot * index + slot / 2
        bars.append(
            PeriodBar(
                label=label,
                x=centre - bar_w / 2,
                y=bottom - height,
                width=bar_w,
                height=height,
                rate=rate,
                saves=saves,
                faced=count,
                empty=count == 0,
            )
        )
    avg_y = bottom - GK_PLOT * competition_save if competition_save is not None else None
    return KeeperPeriodChart(
        width=GK_WIDTH,
        height=GK_HEIGHT,
        left=GK_LEFT,
        right=GK_WIDTH - GK_RIGHT,
        top=GK_TOP,
        bottom=bottom,
        bars=tuple(bars),
        y_ticks=tuple(Tick(bottom - GK_PLOT * p / 100, f"{p}%") for p in (0, 25, 50, 75, 100)),
        avg_y=avg_y,
        side=side,
    )


def _gsaa_momentum(marks: tuple[SaveMark, ...], end: int, side: str) -> GsaaMomentumChart:
    plot_w = GK_WIDTH - GK_LEFT - GK_RIGHT
    bottom = GK_TOP + GK_PLOT

    def x(seconds: float) -> float:
        return GK_LEFT + plot_w * min(max(seconds, 0), end) / end

    running = 0.0
    samples = [(0.0, 0.0)]
    for mark in marks:
        running += mark.gsaa_delta
        samples.append((float(mark.seconds), running))
    if samples[-1][0] < end:
        samples.append((float(end), running))

    peak = max((abs(value) for _, value in samples), default=1.0)
    limit = max(1.0, peak * 1.15)

    def y(value: float) -> float:
        return GK_TOP + GK_PLOT * (1 - (value + limit) / (2 * limit))

    zero = y(0)
    line = "M" + " L".join(f"{x(t):.1f},{y(v):.1f}" for t, v in samples)
    area = f"M{x(samples[0][0]):.1f},{zero:.1f} L" + line[1:] + f" L{x(samples[-1][0]):.1f},{zero:.1f} Z"
    step = 0.5 if limit <= 2 else 1.0 if limit <= 5 else 2.0
    ticks = []
    value = -((limit // step) * step)
    while value <= limit + 1e-9:
        label = "0" if abs(value) < 1e-9 else (f"{value:+.0f}" if abs(value - round(value)) < 1e-9 else f"{value:+.1f}")
        ticks.append(Tick(y(value), label))
        value += step
    minutes = list(range(0, end // 60 + 1, 10))
    return GsaaMomentumChart(
        width=GK_WIDTH,
        height=GK_HEIGHT,
        left=GK_LEFT,
        right=GK_WIDTH - GK_RIGHT,
        top=GK_TOP,
        bottom=bottom,
        zero_y=zero,
        line=line,
        area=area,
        x_ticks=tuple(Tick(x(m * 60), f"{m}'") for m in minutes),
        y_ticks=tuple(ticks),
        half_x=x(REGULATION / 2),
        end_value=running,
        end_pos=(x(end), y(running)),
        side=side,
    )


def _duel_rows(marks: tuple[SaveMark, ...]) -> tuple[DuelRow, ...]:
    buckets: dict[tuple[str, str], list[int]] = {}
    for mark in marks:
        key = (mark.shooter_number, mark.shooter_name or "?")
        line = buckets.setdefault(key, [0, 0])
        line[0] += 1
        line[1] += int(mark.saved)
    rows = [
        DuelRow(number=number, name=name, faced=faced, saves=saves)
        for (number, name), (faced, saves) in buckets.items()
    ]
    rows.sort(key=lambda row: (-row.faced, -(row.rate or 0), row.name))
    return tuple(rows)
