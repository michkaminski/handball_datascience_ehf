"""SVG geometry for the match summary print (units: mm for the flow chart, metres for the court)."""

from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.match_summary import REGULATION, Flow, MatchSummary, PlayerLine, ShotMap, WinCurve, clock

COLORS = {"home": "#4338ca", "away": "#eb6834"}
TINTS = {"home": "#dcdcf5", "away": "#fbdccf"}

# ---------------------------------------------------------------------- flow chart (mm)
FLOW_WIDTH = 190.0
FLOW_LEFT = 13.0
FLOW_RIGHT = 3.0
MARGIN_TOP = 4.6
MARGIN_HEIGHT = 25.0
WIN_TOP = MARGIN_TOP + MARGIN_HEIGHT + 4.4
WIN_HEIGHT = 10.0
AXIS_Y = WIN_TOP + WIN_HEIGHT + 3.2
FLOW_HEIGHT = AXIS_Y + 1.0


@dataclass(frozen=True)
class Tick:
    x: float
    y: float
    label: str


@dataclass(frozen=True)
class Band:
    x: float
    width: float
    side: str
    label: str


@dataclass(frozen=True)
class Marker:
    x: float
    y: float
    side: str
    label: str


@dataclass(frozen=True)
class MomentNote:
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
class FlowChart:
    width: float
    height: float
    left: float
    right: float
    margin_top: float
    margin_bottom: float
    zero_y: float
    margin_path: str
    win_top: float
    win_bottom: float
    win_mid: float
    win_path: str
    win_area: str
    half_x: float
    half_label: str
    time_ticks: tuple[Tick, ...]
    margin_ticks: tuple[Tick, ...]
    bands: tuple[Band, ...]
    timeouts: tuple[Marker, ...]
    suspensions: tuple[Marker, ...]
    moments: tuple[MomentNote, ...]
    axis_y: float


def flow_chart(summary: MatchSummary) -> FlowChart:
    flow = summary.flow
    end = flow.end_seconds
    plot = FLOW_WIDTH - FLOW_LEFT - FLOW_RIGHT

    def x(seconds: float) -> float:
        return FLOW_LEFT + plot * min(max(seconds, 0), end) / end

    biggest = max((abs(g.home - g.away) for g in flow.goals), default=0)
    limit = max(3, biggest + 1)
    zero = MARGIN_TOP + MARGIN_HEIGHT / 2

    def y(margin: int) -> float:
        return zero - margin * (MARGIN_HEIGHT / 2) / limit

    points = [(x(0), y(0))]
    margin = 0
    for goal in flow.goals:
        points.append((x(goal.seconds), y(margin)))
        margin = goal.home - goal.away
        points.append((x(goal.seconds), y(margin)))
    points.append((x(end), y(margin)))
    area = [(x(0), zero)] + points + [(x(end), zero)]
    margin_path = "M" + " L".join(f"{px:.2f},{py:.2f}" for px, py in area) + " Z"

    step = 2 if limit <= 6 else 4 if limit <= 12 else 6
    margin_ticks = tuple(
        Tick(FLOW_LEFT - 1.2, y(value), f"+{abs(value)}" if value else "0")
        for value in range(-limit + (limit % step), limit + 1, step)
        if abs(value) < limit or value == 0
    )
    minutes = list(range(0, end // 60 + 1, 10))
    if end > REGULATION:
        minutes = list(range(0, 61, 10)) + [65, end // 60]
    time_ticks = tuple(Tick(x(m * 60), AXIS_Y, f"{m}'") for m in minutes)

    win_path, win_area = _win_paths(summary.win, x)
    half_score = (
        f"{summary.header.half_time_home}:{summary.header.half_time_away}"
        if summary.header.half_time_home is not None
        else ""
    )
    return FlowChart(
        width=FLOW_WIDTH,
        height=FLOW_HEIGHT,
        left=FLOW_LEFT,
        right=FLOW_WIDTH - FLOW_RIGHT,
        margin_top=MARGIN_TOP,
        margin_bottom=MARGIN_TOP + MARGIN_HEIGHT,
        zero_y=zero,
        margin_path=margin_path,
        win_top=WIN_TOP,
        win_bottom=WIN_TOP + WIN_HEIGHT,
        win_mid=WIN_TOP + WIN_HEIGHT / 2,
        win_path=win_path,
        win_area=win_area,
        half_x=x(REGULATION / 2),
        half_label=half_score,
        time_ticks=time_ticks,
        margin_ticks=margin_ticks,
        bands=tuple(
            Band(x(run.start), max(x(run.end) - x(run.start), 0.8), run.side, f"{run.goals}:0") for run in flow.runs
        ),
        timeouts=_spread([Marker(x(t.seconds), MARGIN_TOP - 2.6, t.side or "home", "T") for t in flow.timeouts]),
        suspensions=tuple(_suspensions(summary, x)),
        moments=_spread_moments(
            [
                MomentNote(
                    number=index,
                    x=x(moment.seconds),
                    y=y(moment.home - moment.away),
                    side=moment.side,
                    clock=clock(moment.seconds),
                    who=moment.scorer.name if moment.scorer else "",
                    score=f"{moment.home}:{moment.away}",
                    before=f"{moment.before:.0%}",
                    after=f"{moment.after:.0%}",
                )
                for index, moment in enumerate(summary.win.moments, start=1)
            ]
        ),
        axis_y=AXIS_Y,
    )


def _spread(markers: list[Marker], gap: float = 3.1) -> tuple[Marker, ...]:
    """Push apart timeout markers that would overlap (two timeouts seconds apart)."""
    placed: list[Marker] = []
    for marker in markers:
        if placed and marker.x - placed[-1].x < gap:
            shift = (gap - (marker.x - placed[-1].x)) / 2
            previous = placed.pop()
            placed.append(Marker(previous.x - shift, previous.y, previous.side, previous.label))
            marker = Marker(marker.x + shift, marker.y, marker.side, marker.label)
        placed.append(marker)
    return tuple(placed)


def _spread_moments(notes: list[MomentNote], gap: float = 3.6) -> tuple[MomentNote, ...]:
    """Keep the numbered moment circles apart; a moved circle stays at its goal's height."""
    placed: list[MomentNote] = []
    for note in notes:
        if placed and note.x - placed[-1].x < gap and abs(note.y - placed[-1].y) < gap:
            note = MomentNote(**{**note.__dict__, "x": placed[-1].x + gap})
        placed.append(note)
    right = FLOW_WIDTH - FLOW_RIGHT
    if placed and placed[-1].x > right:
        shift = placed[-1].x - right
        placed = [MomentNote(**{**n.__dict__, "x": n.x - shift}) if n.x > right - gap * len(placed) else n for n in placed]
    return tuple(placed)


def _win_paths(win: WinCurve, x) -> tuple[str, str]:
    def y(p: float) -> float:
        return WIN_TOP + WIN_HEIGHT * (1 - p)

    line = "M" + " L".join(f"{x(t):.2f},{y(p):.2f}" for t, p in win.points)
    mid = WIN_TOP + WIN_HEIGHT / 2
    first, last = win.points[0][0], win.points[-1][0]
    area = f"M{x(first):.2f},{mid:.2f} L" + line[1:] + f" L{x(last):.2f},{mid:.2f} Z"
    return line, area


def _suspensions(summary: MatchSummary, x) -> list[Marker]:
    y = MARGIN_TOP + MARGIN_HEIGHT + 2.2
    marks = [Marker(x(m.seconds), y, m.side, "2'") for m in summary.suspensions]
    marks += [Marker(x(m.seconds), y, m.side, "R") for m in summary.red_cards]
    return marks


# ---------------------------------------------------------------------- court (metres)
ZONE_SPOTS = {
    "LW": (1.5, 1.7),
    "RW": (18.5, 1.7),
    "LSD": (4.4, 6.0),
    "CSD": (10.0, 7.5),
    "RSD": (15.6, 6.0),
    "LLD": (3.0, 10.7),
    "CLD": (10.0, 11.0),
    "RLD": (17.0, 10.7),
}


@dataclass(frozen=True)
class ZoneSpot:
    x: float
    y: float
    goals: int
    shots: int
    rate: str
    fill: str
    ink: str
    empty: bool
    zone: str = ""


def court_spots(shot_map: ShotMap) -> tuple[ZoneSpot, ...]:
    spots = []
    for zone, (x, y) in ZONE_SPOTS.items():
        cell = shot_map.cells[zone]
        rate = cell.rate
        share = rate if rate is not None else 0.0
        fill = _mix("#ffffff", COLORS[shot_map.side], 0.12 + 0.88 * share) if cell.shots else "#ffffff"
        spots.append(
            ZoneSpot(
                zone=zone,
                x=x,
                y=y,
                goals=cell.goals,
                shots=cell.shots,
                rate=f"{rate:.0%}" if rate is not None else "",
                fill=fill,
                ink="#ffffff" if cell.shots and _luminance(fill) < 0.42 else "#111111",
                empty=cell.shots == 0,
            )
        )
    return tuple(spots)


def scale_stops(side: str) -> tuple[str, ...]:
    return tuple(_mix("#ffffff", COLORS[side], 0.12 + 0.88 * step / 4) for step in range(5))


def _mix(start: str, end: str, share: float) -> str:
    a = [int(start[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(p + (q - p) * share):02x}" for p, q in zip(a, b))


def _luminance(color: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(int(color[i : i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---------------------------------------------------------------------- small pieces


def goal_dots(line: PlayerLine, end: int) -> tuple[float, ...]:
    """Dot positions (0–100) of a player's goals on a strip covering the match."""
    return tuple(2 + 96 * seconds / end for seconds in line.goal_seconds)


def segment_bars(flow: Flow) -> tuple[tuple[str, int, int, float, float], ...]:
    top = max((max(h, a) for _, h, a in flow.segments), default=1) or 1
    return tuple((label, h, a, h / top, a / top) for label, h, a in flow.segments)


# ---------------------------------------------------------------------- short version: one bar chart (mm)
LEAD_HEIGHT = 50.0
LEAD_TOP = 5.0
LEAD_BOTTOM = LEAD_HEIGHT - 5.0


@dataclass(frozen=True)
class LeadBar:
    x: float
    y: float
    width: float
    height: float
    side: str


@dataclass(frozen=True)
class Peak:
    x: float
    y: float
    label_x: float
    label_y: float
    side: str
    margin: str
    score: str
    minute: str


@dataclass(frozen=True)
class LeadChart:
    width: float
    height: float
    left: float
    right: float
    top: float
    bottom: float
    zero_y: float
    bars: tuple[LeadBar, ...]
    margin_ticks: tuple[Tick, ...]
    time_ticks: tuple[Tick, ...]
    half_x: float
    half_label: str
    peaks: tuple[Peak, ...]


def lead_chart(summary: MatchSummary) -> LeadChart:
    """Goal difference per minute as a bar (home up, away down), the two biggest leads marked."""
    flow = summary.flow
    end = flow.end_seconds
    minutes = end // 60
    plot = FLOW_WIDTH - FLOW_LEFT - FLOW_RIGHT
    slot = plot / minutes
    # each side gets the room its own biggest lead needs (at least 3 goals), so one-sided games use the height
    up = max(3, max((g.home - g.away for g in flow.goals), default=0) + 2)
    down = max(3, max((g.away - g.home for g in flow.goals), default=0) + 2)
    per_goal = (LEAD_BOTTOM - LEAD_TOP) / (up + down)
    zero = LEAD_TOP + up * per_goal

    def y(margin: float) -> float:
        return zero - margin * per_goal

    bars = []
    margin = 0
    index = 0
    for minute in range(minutes):
        # the biggest difference reached in the minute (the later one when two are equal), so a lead
        # that lasted seconds still shows and the marked biggest leads sit on top of their bars
        shown = margin
        while index < len(flow.goals) and flow.goals[index].seconds <= (minute + 1) * 60:
            margin = flow.goals[index].home - flow.goals[index].away
            if abs(margin) >= abs(shown):
                shown = margin
            index += 1
        if shown:
            bars.append(
                LeadBar(
                    x=FLOW_LEFT + minute * slot + slot * 0.12,
                    y=min(y(shown), zero),
                    width=slot * 0.76,
                    height=abs(y(shown) - zero),
                    side="home" if shown > 0 else "away",
                )
            )

    span = up + down
    step = 1 if span <= 8 else 2 if span <= 16 else 4 if span <= 32 else 6
    margin_ticks = tuple(
        Tick(FLOW_LEFT - 1.2, y(value), f"+{abs(value)}" if value else "0")
        for value in range(-(down // step) * step, up + 1, step)
    )
    marks = list(range(0, 61, 10)) + ([65, minutes] if end > REGULATION else [])
    time_ticks = tuple(Tick(FLOW_LEFT + plot * m * 60 / end, LEAD_HEIGHT - 1.4, f"{m}'") for m in marks)

    peaks = []
    for side in ("home", "away"):
        lead = flow.biggest[side]
        if lead is None:
            continue
        value = lead.margin if side == "home" else -lead.margin
        x = FLOW_LEFT + (lead.seconds // 60) * slot + slot / 2
        peak_y = y(value)
        peaks.append(
            Peak(
                x=x,
                y=peak_y,
                # keep the label (about 18 mm wide) inside the plot near the edges
                label_x=min(max(x, FLOW_LEFT + 10), FLOW_WIDTH - FLOW_RIGHT - 10),
                label_y=peak_y - 1.6 if side == "home" else peak_y + 3.6,
                side=side,
                margin=f"+{lead.margin}",
                score=f"{lead.home}:{lead.away}",
                minute=f"{lead.seconds // 60 + 1}'",
            )
        )
    half = summary.header
    return LeadChart(
        width=FLOW_WIDTH,
        height=LEAD_HEIGHT,
        left=FLOW_LEFT,
        right=FLOW_WIDTH - FLOW_RIGHT,
        top=LEAD_TOP,
        bottom=LEAD_BOTTOM,
        zero_y=zero,
        bars=tuple(bars),
        margin_ticks=margin_ticks,
        time_ticks=time_ticks,
        half_x=FLOW_LEFT + plot * (REGULATION / 2) / end,
        half_label=f"{half.half_time_home}:{half.half_time_away}" if half.half_time_home is not None else "",
        peaks=tuple(peaks),
    )
