"""Charts of the Play-by-play tab, read with the same rules as the match summary print.

Geometry is in SVG user units of a fixed-width viewBox (the page scales it to the column width).
"""

from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.match_summary import (
    REGULATION,
    Flow,
    TickerAction,
    TickerActor,
    match_events,
    match_flow,
)
from ehf.domain.play_by_play import PlayAction

WIDTH = 960.0
PAD_LEFT = 46.0
PAD_RIGHT = 18.0
PLOT_WIDTH = WIDTH - PAD_LEFT - PAD_RIGHT

LEAD_TOP = 30.0
LEAD_PLOT = 210.0
LEAD_HEIGHT = LEAD_TOP + LEAD_PLOT + 54.0  # minute labels, then the score every 5 minutes
TIE_HALF = 4.5

SMALL_WIDTH = 470.0
SMALL_LEFT = 38.0
SMALL_RIGHT = 44.0
SMALL_TOP = 22.0
SMALL_PLOT = 168.0
SMALL_HEIGHT = SMALL_TOP + SMALL_PLOT + 34.0


@dataclass(frozen=True)
class Tick:
    pos: float
    label: str
    side: str = ""


@dataclass(frozen=True)
class MinuteBar:
    x: float
    y: float
    width: float
    height: float
    side: str
    minute: int
    margin: int
    score: str


@dataclass(frozen=True)
class Peak:
    x: float
    y: float
    label_x: float
    label_y: float
    side: str
    margin: int
    score: str
    minute: int


@dataclass(frozen=True)
class LeadChart:
    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float
    zero_y: float
    bars: tuple[MinuteBar, ...]
    y_ticks: tuple[Tick, ...]
    x_ticks: tuple[Tick, ...]
    minor_x: tuple[float, ...]
    half_x: float
    half_label: str
    peaks: tuple[Peak, ...]
    score_marks: tuple[Tick, ...] = ()


@dataclass(frozen=True)
class ScoreDot:
    x: float
    y: float


@dataclass(frozen=True)
class ScoreChart:
    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float
    home_path: str
    away_path: str
    home_area: str
    away_area: str
    home_dots: tuple[ScoreDot, ...]
    away_dots: tuple[ScoreDot, ...]
    home_end: tuple[float, float, int]
    away_end: tuple[float, float, int]
    y_ticks: tuple[Tick, ...]
    x_ticks: tuple[Tick, ...]
    half_x: float


@dataclass(frozen=True)
class SegmentBar:
    label: str
    home: int
    away: int
    home_x: float
    away_x: float
    width: float
    home_y: float
    away_y: float
    label_x: float


@dataclass(frozen=True)
class SegmentChart:
    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float
    bars: tuple[SegmentBar, ...]
    y_ticks: tuple[Tick, ...]


@dataclass(frozen=True)
class FlowFacts:
    ties: int
    lead_changes: int
    biggest: dict[str, tuple[int, str, int] | None]


@dataclass(frozen=True)
class PlayCharts:
    lead: LeadChart | None = None
    score: ScoreChart | None = None
    segments: SegmentChart | None = None
    facts: FlowFacts | None = None

    @property
    def ready(self) -> bool:
        return self.lead is not None


def ticker_actions(actions: tuple[PlayAction, ...]) -> tuple[TickerAction, ...]:
    """The tab's actions in the shape the match-summary rules read (actions without a clock are left out)."""
    return tuple(
        TickerAction(
            seq=action.seq,
            code=action.action_code,
            result=action.result_code,
            zone=action.shot_zone,
            add=action.action_add,
            period=action.period_code,
            seconds=action.seconds,
            home=action.score_home,
            away=action.score_away,
            actors=tuple(
                TickerActor(
                    person.side,
                    person.role_code,
                    person.shirt_number,
                    person.last_name or person.first_name,
                    person.person_id,
                )
                for person in action.participants
            ),
        )
        for action in actions
        if action.seconds is not None
    )


def build_play_charts(actions: tuple[PlayAction, ...], half_time: str = "") -> PlayCharts:
    ticker = ticker_actions(actions)
    if not ticker:
        return PlayCharts()
    flow = match_flow(match_events(ticker))
    if not flow.goals:
        return PlayCharts()
    return PlayCharts(
        lead=_lead_chart(flow, half_time),
        score=_score_chart(flow),
        segments=_segment_chart(flow),
        facts=FlowFacts(
            ties=flow.ties,
            lead_changes=flow.lead_changes,
            biggest={
                side: (lead.margin, f"{lead.home}:{lead.away}", lead.seconds // 60 + 1) if lead else None
                for side, lead in flow.biggest.items()
            },
        ),
    )


# --------------------------------------------------------------------------- goal difference per minute


def _lead_chart(flow: Flow, half_time: str) -> LeadChart:
    end = flow.end_seconds
    minutes = end // 60
    slot = PLOT_WIDTH / minutes
    up = max(3, max((g.home - g.away for g in flow.goals), default=0) + 1)
    down = max(3, max((g.away - g.home for g in flow.goals), default=0) + 1)
    per_goal = LEAD_PLOT / (up + down)
    zero = LEAD_TOP + up * per_goal

    def y(margin: float) -> float:
        return zero - margin * per_goal

    bars = []
    margin = 0
    index = 0
    score = "0:0"
    for minute in range(minutes):
        # the biggest difference reached in the minute (the later one of equals): a lead of seconds still shows
        shown = margin
        shown_score = score
        while index < len(flow.goals) and flow.goals[index].seconds <= (minute + 1) * 60:
            goal = flow.goals[index]
            margin = goal.home - goal.away
            score = f"{goal.home}:{goal.away}"
            if abs(margin) >= abs(shown):
                shown, shown_score = margin, score
            index += 1
        if shown:
            bars.append(
                MinuteBar(
                    x=PAD_LEFT + minute * slot + slot * 0.14,
                    y=min(y(shown), zero),
                    width=slot * 0.72,
                    height=abs(y(shown) - zero),
                    side="home" if shown > 0 else "away",
                    minute=minute + 1,
                    margin=abs(shown),
                    score=shown_score,
                )
            )
        else:
            bars.append(
                MinuteBar(
                    x=PAD_LEFT + minute * slot + slot * 0.22,
                    y=zero - TIE_HALF,
                    width=slot * 0.56,
                    height=TIE_HALF * 2,
                    side="tie",
                    minute=minute + 1,
                    margin=0,
                    score=shown_score,
                )
            )

    span = up + down
    step = 1 if span <= 8 else 2 if span <= 16 else 4 if span <= 32 else 6
    y_ticks = tuple(
        Tick(y(value), f"+{abs(value)}" if value else "0", "home" if value > 0 else "away" if value < 0 else "")
        for value in range(-(down // step) * step, up + 1, step)
    )
    x_ticks = tuple(Tick(PAD_LEFT + slot * m, f"{m}'") for m in range(0, minutes + 1, 10))
    minor_x = tuple(PAD_LEFT + slot * m for m in range(5, minutes, 10))

    peaks = []
    for side in ("home", "away"):
        lead = flow.biggest[side]
        if lead is None:
            continue
        value = lead.margin if side == "home" else -lead.margin
        x = PAD_LEFT + (lead.seconds // 60) * slot + slot / 2
        peaks.append(
            Peak(
                x=x,
                y=y(value),
                label_x=min(max(x, PAD_LEFT + 60), WIDTH - PAD_RIGHT - 60),
                label_y=y(value) - 9 if side == "home" else y(value) + 18,
                side=side,
                margin=lead.margin,
                score=f"{lead.home}:{lead.away}",
                minute=lead.seconds // 60 + 1,
            )
        )
    score_marks = []
    for minute in range(5, minutes + 1, 5):
        home = away = 0
        for goal in flow.goals:
            if goal.seconds > minute * 60:
                break
            home, away = goal.home, goal.away
        side = "home" if home > away else "away" if away > home else "tie"
        score_marks.append(Tick(PAD_LEFT + slot * minute, f"{home}:{away}", side))
    return LeadChart(
        width=WIDTH,
        height=LEAD_HEIGHT,
        left=PAD_LEFT,
        right=WIDTH - PAD_RIGHT,
        top=LEAD_TOP,
        bottom=LEAD_TOP + LEAD_PLOT,
        zero_y=zero,
        bars=tuple(bars),
        y_ticks=y_ticks,
        x_ticks=x_ticks,
        minor_x=minor_x,
        half_x=PAD_LEFT + PLOT_WIDTH * (REGULATION / 2) / end,
        half_label=half_time,
        peaks=tuple(peaks),
        score_marks=tuple(score_marks),
    )


# --------------------------------------------------------------------------- running score


def _score_chart(flow: Flow) -> ScoreChart:
    end = flow.end_seconds
    plot_w = SMALL_WIDTH - SMALL_LEFT - SMALL_RIGHT
    bottom = SMALL_TOP + SMALL_PLOT
    last = flow.goals[-1]
    top_goals = max(last.home, last.away, 1)
    step = 5 if top_goals <= 40 else 10
    ceiling = ((top_goals + 1 + step - 1) // step) * step  # room above the final score

    def x(seconds: int) -> float:
        return SMALL_LEFT + plot_w * min(seconds, end) / end

    def y(goals: int) -> float:
        return SMALL_TOP + SMALL_PLOT * (1 - goals / ceiling)

    def series(side: str) -> tuple[str, str, tuple[ScoreDot, ...], tuple[float, float, int]]:
        count = 0
        parts = [f"M{x(0):.1f},{y(0):.1f}"]
        dots = [ScoreDot(x(0), y(0))]
        for goal in flow.goals:
            if goal.side != side:
                continue
            parts.append(f"H{x(goal.seconds):.1f}")
            count += 1
            parts.append(f"V{y(count):.1f}")
            dots.append(ScoreDot(x(goal.seconds), y(count)))
        parts.append(f"H{x(end):.1f}")
        line = " ".join(parts)
        area = f"M{x(0):.1f},{bottom:.1f} L" + line[1:] + f" L{x(end):.1f},{bottom:.1f} Z"
        return line, area, tuple(dots), (x(end), y(count), count)

    home_path, home_area, home_dots, home_end = series("home")
    away_path, away_area, away_dots, away_end = series("away")
    return ScoreChart(
        width=SMALL_WIDTH,
        height=SMALL_HEIGHT,
        left=SMALL_LEFT,
        right=SMALL_WIDTH - SMALL_RIGHT,
        top=SMALL_TOP,
        bottom=bottom,
        home_path=home_path,
        away_path=away_path,
        home_area=home_area,
        away_area=away_area,
        home_dots=home_dots,
        away_dots=away_dots,
        home_end=home_end,
        away_end=away_end,
        y_ticks=tuple(Tick(y(value), str(value)) for value in range(0, ceiling + 1, step)),
        x_ticks=tuple(Tick(x(m * 60), f"{m}'") for m in range(0, end // 60 + 1, 10)),
        half_x=x(REGULATION // 2),
    )


# --------------------------------------------------------------------------- goals per 10 minutes


def _segment_chart(flow: Flow) -> SegmentChart:
    plot_w = SMALL_WIDTH - SMALL_LEFT - 10
    count = len(flow.segments)
    slot = plot_w / count
    top = max((max(h, a) for _, h, a in flow.segments), default=1) or 1
    ceiling = top + 1

    def y(goals: int) -> float:
        return SMALL_TOP + SMALL_PLOT * (1 - goals / ceiling)

    bar = slot * 0.3
    bars = []
    for index, (label, home, away) in enumerate(flow.segments):
        centre = SMALL_LEFT + slot * index + slot / 2
        bars.append(
            SegmentBar(
                label="ET" if label == "ET" else label,
                home=home,
                away=away,
                home_x=centre - bar - 1.5,
                away_x=centre + 1.5,
                width=bar,
                home_y=y(home),
                away_y=y(away),
                label_x=centre,
            )
        )
    step = 1 if ceiling <= 6 else 2 if ceiling <= 12 else 4
    return SegmentChart(
        width=SMALL_WIDTH,
        height=SMALL_HEIGHT,
        left=SMALL_LEFT,
        right=SMALL_WIDTH - 10,
        top=SMALL_TOP,
        bottom=SMALL_TOP + SMALL_PLOT,
        bars=tuple(bars),
        y_ticks=tuple(Tick(y(value), str(value)) for value in range(0, ceiling + 1, step)),
    )

