from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.play_by_play import PlayAction, PlayRow, clock_label, event_row, is_visible, period_seconds
from ehf.domain.play_charts import PlayCharts, build_play_charts

PERIOD_TITLES = {
    "H1": "1st half",
    "H2": "2nd half",
    "ET1": "Extra time 1",
    "ET2": "Extra time 2",
    "SO": "7m shootout",
    "P7": "7m shootout",
}

TICK_MARKS = (10 * 60, 20 * 60)


@dataclass(frozen=True)
class PlayTimeline:
    rows: tuple[PlayRow, ...]
    charts: PlayCharts
    home_name: str
    away_name: str


def present_timeline(
    actions: tuple[PlayAction, ...],
    home_name: str,
    away_name: str,
) -> PlayTimeline:
    visible = tuple(action for action in actions if is_visible(action))
    rows, marks = _rows(visible)
    return PlayTimeline(
        rows=tuple(_with_moments(rows, marks, home_name, away_name)),
        charts=build_play_charts(visible),
        home_name=home_name,
        away_name=away_name,
    )


def _rows(actions: tuple[PlayAction, ...]) -> tuple[list[PlayRow], list[tuple[int, int, PlayAction]]]:
    rows: list[PlayRow] = []
    marks: list[tuple[int, int, PlayAction]] = []
    period: str | None = None
    seen_ticks: set[int] = set()
    previous = (0, 0)
    for action in actions:
        if action.action_code != "ENDP" and action.period_code and action.period_code != period:
            period = action.period_code
            seen_ticks = set()
            rows.append(PlayRow(kind="period", title=PERIOD_TITLES.get(period, period)))
        if action.action_code != "STARTP":
            _ticks(rows, seen_ticks, action, previous)
        score = (action.score_home, action.score_away)
        if action.action_code == "STARTP":
            previous = score
            continue
        if action.action_code == "ENDP":
            title = "Full time" if action.action_add == "END" else "Half-time"
            rows.append(PlayRow(kind="close", title=title, score=f"{score[0]}:{score[1]}"))
            previous = score
            continue
        rows.append(event_row(action))
        if score != previous:
            marks.append((len(rows) - 1, score[0] - score[1], action))
        previous = score
    return rows, marks


def _ticks(rows: list[PlayRow], seen: set[int], action: PlayAction, previous: tuple[int, int]) -> None:
    seconds = period_seconds(action.clock_raw)
    if seconds is None:
        return
    for mark in TICK_MARKS:
        if seconds < mark or mark in seen:
            continue
        seen.add(mark)
        minutes = mark // 60
        rows.append(PlayRow(kind="tick", clock=f"{minutes:02d}:00", score=f"{previous[0]}:{previous[1]}"))


def _with_moments(
    rows: list[PlayRow],
    marks: list[tuple[int, int, PlayAction]],
    home_name: str,
    away_name: str,
) -> list[PlayRow]:
    if not marks:
        return rows
    peak = max(abs(diff) for _, diff, _ in marks)
    best_tie = max((action.score_home + action.score_away for _, diff, action in marks if diff == 0), default=0)
    inserts: list[tuple[int, PlayRow]] = []
    seen_home = False
    seen_away = False
    seen_peak = False
    seen_tie = False
    previous = 0
    for index, diff, action in marks:
        if not seen_home and previous <= 0 < diff:
            inserts.append((index, _moment(f"First lead · {home_name}", action)))
            seen_home = True
        if not seen_away and previous >= 0 > diff:
            inserts.append((index, _moment(f"First lead · {away_name}", action)))
            seen_away = True
        if not seen_peak and peak >= 2 and abs(diff) == peak:
            leader = home_name if diff > 0 else away_name
            detail = f"{leader} +{abs(diff)} · {clock_label(action.clock_raw)}"
            inserts.append((index, _moment("Highest lead", action, detail)))
            seen_peak = True
        if (
            not seen_tie
            and diff == 0
            and previous != 0
            and action.score_home + action.score_away == best_tie
        ):
            inserts.append((index, _moment("Level", action)))
            seen_tie = True
        previous = diff
    for index, item in reversed(inserts):
        rows.insert(index + 1, item)
    return rows


def _moment(title: str, action: PlayAction, detail: str | None = None) -> PlayRow:
    clock = clock_label(action.clock_raw)
    score = f"{action.score_home}:{action.score_away}"
    return PlayRow(kind="moment", title=title, detail=detail or f"{score} · {clock}")
