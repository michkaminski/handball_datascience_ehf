"""Geometry and display values for the Statistics tab of the match card (SVG user units = px)."""

from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.match_statistics import MatchStatistics, PlayerStats, SaveMark
from ehf.domain.match_summary import REGULATION, ComparisonRow, MatchSummary, clock

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
