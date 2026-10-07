from __future__ import annotations

from dataclasses import dataclass

from ehf.domain.play_by_play import PlayAction, period_seconds

PERIOD_OFFSETS = {
    "H1": 0,
    "H2": 30 * 60,
    "ET1": 60 * 60,
    "ET2": 70 * 60,
    "SO": 80 * 60,
    "P7": 80 * 60,
}

MATCH_MINUTES = 60
BUCKET_COUNT = 12
PAD_L = 34.0
PAD_R = 44.0
PAD_T = 16.0
PAD_B = 26.0
PLOT_W = 560.0
PLOT_H = 132.0
WIDTH = PAD_L + PLOT_W + PAD_R
HEIGHT = PAD_T + PLOT_H + PAD_B


@dataclass(frozen=True)
class ChartTick:
    pos: float
    label: str


@dataclass(frozen=True)
class ChartMark:
    x: float
    y: float
    text: str
    anchor: str = "middle"


@dataclass(frozen=True)
class LeadChart:
    polyline: str
    zero_y: float
    ht_x: float
    band_home_h: float
    band_away_y: float
    band_away_h: float
    y_ticks: tuple[ChartTick, ...]
    x_ticks: tuple[ChartTick, ...]
    max_home: ChartMark | None
    max_away: ChartMark | None
    final: ChartMark | None
    width: float = WIDTH
    height: float = HEIGHT
    plot_left: float = PAD_L
    plot_top: float = PAD_T
    plot_width: float = PLOT_W
    plot_height: float = PLOT_H


@dataclass(frozen=True)
class ScoreChart:
    home_line: str
    away_line: str
    ht_x: float
    y_ticks: tuple[ChartTick, ...]
    x_ticks: tuple[ChartTick, ...]
    home_end: ChartMark
    away_end: ChartMark
    width: float = WIDTH
    height: float = HEIGHT
    plot_left: float = PAD_L
    plot_top: float = PAD_T
    plot_width: float = PLOT_W
    plot_height: float = PLOT_H


@dataclass(frozen=True)
class BucketBar:
    label: str
    home: int
    away: int
    home_x: float
    home_y: float
    home_w: float
    home_h: float
    away_x: float
    away_y: float
    away_w: float
    away_h: float
    label_x: float


@dataclass(frozen=True)
class BucketChart:
    bars: tuple[BucketBar, ...]
    y_ticks: tuple[ChartTick, ...]
    baseline_y: float
    width: float = WIDTH
    height: float = HEIGHT
    plot_left: float = PAD_L
    plot_top: float = PAD_T
    plot_width: float = PLOT_W
    plot_height: float = PLOT_H


@dataclass(frozen=True)
class PlayCharts:
    lead: LeadChart | None
    score: ScoreChart | None
    buckets: BucketChart | None

    @property
    def ready(self) -> bool:
        return self.lead is not None or self.score is not None or self.buckets is not None


def build_play_charts(actions: tuple[PlayAction, ...]) -> PlayCharts:
    series = _score_series(actions)
    if not series:
        return PlayCharts(lead=None, score=None, buckets=None)
    return PlayCharts(
        lead=_lead_chart(series),
        score=_score_chart(series),
        buckets=_bucket_chart(series),
    )


def _score_series(actions: tuple[PlayAction, ...]) -> list[tuple[float, int, int]]:
    points = [(0.0, 0, 0)]
    current = (0, 0)
    last_t = 0.0
    for action in actions:
        if action.action_code == "STARTP":
            continue
        elapsed = _elapsed(action)
        if elapsed is None:
            elapsed = last_t
        score = (action.score_home, action.score_away)
        if score != current:
            points.append((elapsed, score[0], score[1]))
            current = score
        last_t = max(last_t, elapsed)
    end = max(float(MATCH_MINUTES * 60), last_t)
    if points[-1][0] < end or points[-1][1:] != current:
        points.append((end, current[0], current[1]))
    return points


def _lead_chart(series: list[tuple[float, int, int]]) -> LeadChart:
    diffs = [home - away for _, home, away in series]
    peak = max(1, max(abs(value) for value in diffs))
    zero_y = PAD_T + PLOT_H / 2
    step = _lead_step(series, peak, zero_y)
    max_home_i = max(range(len(diffs)), key=lambda i: diffs[i])
    max_away_i = min(range(len(diffs)), key=lambda i: diffs[i])
    max_home = None
    if diffs[max_home_i] > 0:
        x, y = _xy(series[max_home_i][0], diffs[max_home_i], peak, zero_y)
        max_home = ChartMark(x=x, y=max(PAD_T + 10, y - 8), text=f"max +{diffs[max_home_i]}", anchor="middle")
    max_away = None
    if diffs[max_away_i] < 0:
        x, y = _xy(series[max_away_i][0], diffs[max_away_i], peak, zero_y)
        max_away = ChartMark(x=x, y=min(PAD_T + PLOT_H - 4, y + 12), text=f"max +{-diffs[max_away_i]}", anchor="middle")
    final_diff = diffs[-1]
    fx, fy = _xy(series[-1][0], final_diff, peak, zero_y)
    final_text = f"{final_diff:+d}" if final_diff != 0 else "0"
    return LeadChart(
        polyline=step,
        zero_y=zero_y,
        ht_x=_x(30 * 60),
        band_home_h=PLOT_H / 2,
        band_away_y=zero_y,
        band_away_h=PLOT_H / 2,
        y_ticks=_lead_y_ticks(peak, zero_y),
        x_ticks=_minute_ticks(),
        max_home=max_home,
        max_away=max_away,
        final=ChartMark(x=min(WIDTH - 6, fx + 8), y=fy + 3, text=final_text, anchor="start"),
    )


def _score_chart(series: list[tuple[float, int, int]]) -> ScoreChart:
    top = max(1, max(max(home, away) for _, home, away in series))
    home_pts = [_xy_score(t, home, top) for t, home, _ in _step_scores(series, "home")]
    away_pts = [_xy_score(t, away, top) for t, _, away in _step_scores(series, "away")]
    home_end = home_pts[-1]
    away_end = away_pts[-1]
    home_label_y = home_end[1] - 2
    away_label_y = away_end[1] + 10
    if abs(home_label_y - away_label_y) < 10:
        if home_end[1] <= away_end[1]:
            home_label_y = home_end[1] - 4
            away_label_y = away_end[1] + 12
        else:
            away_label_y = away_end[1] - 4
            home_label_y = home_end[1] + 12
    return ScoreChart(
        home_line=_poly(home_pts),
        away_line=_poly(away_pts),
        ht_x=_x(30 * 60),
        y_ticks=_score_y_ticks(top),
        x_ticks=_minute_ticks(),
        home_end=ChartMark(x=min(WIDTH - 6, home_end[0] + 6), y=home_label_y, text=str(series[-1][1]), anchor="start"),
        away_end=ChartMark(x=min(WIDTH - 6, away_end[0] + 6), y=away_label_y, text=str(series[-1][2]), anchor="start"),
    )


def _bucket_chart(series: list[tuple[float, int, int]]) -> BucketChart:
    home_counts = [0] * BUCKET_COUNT
    away_counts = [0] * BUCKET_COUNT
    previous = (0, 0)
    for t, home, away in series[1:]:
        index = min(BUCKET_COUNT - 1, int(t // 300))
        if home > previous[0]:
            home_counts[index] += home - previous[0]
        if away > previous[1]:
            away_counts[index] += away - previous[1]
        previous = (home, away)
    top = max(1, max(*home_counts, *away_counts))
    group_w = PLOT_W / BUCKET_COUNT
    bar_w = group_w * 0.32
    gap = group_w * 0.08
    bars: list[BucketBar] = []
    for index in range(BUCKET_COUNT):
        left = PAD_L + index * group_w
        home = home_counts[index]
        away = away_counts[index]
        home_h = home / top * (PLOT_H - 8)
        away_h = away / top * (PLOT_H - 8)
        home_x = left + group_w * 0.18
        away_x = home_x + bar_w + gap
        start = 0 if index == 0 else index * 5 + 1
        end = (index + 1) * 5
        bars.append(
            BucketBar(
                label=f"{start}–{end}",
                home=home,
                away=away,
                home_x=home_x,
                home_y=PAD_T + PLOT_H - home_h,
                home_w=bar_w,
                home_h=home_h,
                away_x=away_x,
                away_y=PAD_T + PLOT_H - away_h,
                away_w=bar_w,
                away_h=away_h,
                label_x=left + group_w / 2,
            )
        )
    return BucketChart(
        bars=tuple(bars),
        y_ticks=_score_y_ticks(top),
        baseline_y=PAD_T + PLOT_H,
    )


def _lead_step(series: list[tuple[float, int, int]], peak: int, zero_y: float) -> str:
    points: list[tuple[float, float]] = []
    previous_diff = 0
    for t, home, away in series:
        diff = home - away
        if points:
            points.append((_x(t), _y(previous_diff, peak, zero_y)))
        points.append((_x(t), _y(diff, peak, zero_y)))
        previous_diff = diff
    return _poly(points)


def _step_scores(
    series: list[tuple[float, int, int]],
    side: str,
) -> list[tuple[float, int, int]]:
    points: list[tuple[float, int, int]] = []
    previous = series[0]
    for point in series:
        if side == "home" and point[1] != previous[1]:
            points.append((point[0], previous[1], previous[2]))
        if side == "away" and point[2] != previous[2]:
            points.append((point[0], previous[1], previous[2]))
        points.append(point)
        previous = point
    return points


def _lead_y_ticks(peak: int, zero_y: float) -> tuple[ChartTick, ...]:
    values = (peak, 0, -peak) if peak <= 3 else (peak, peak // 2, 0, -(peak // 2), -peak)
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return tuple(ChartTick(_y(value, peak, zero_y), f"{value:+d}" if value != 0 else "0") for value in unique)


def _score_y_ticks(top: int) -> tuple[ChartTick, ...]:
    if top <= 4:
        values = list(range(top, -1, -1))
    else:
        step = max(1, round(top / 4))
        values = list(range(top, -1, -step))
        if values[-1] != 0:
            values.append(0)
    return tuple(ChartTick(PAD_T + (1 - value / top) * PLOT_H, str(value)) for value in values)


def _minute_ticks() -> tuple[ChartTick, ...]:
    return tuple(ChartTick(_x(minute * 60), str(minute)) for minute in (0, 15, 30, 45, 60))


def _xy(seconds: float, diff: int, peak: int, zero_y: float) -> tuple[float, float]:
    return _x(seconds), _y(diff, peak, zero_y)


def _xy_score(seconds: float, goals: int, top: int) -> tuple[float, float]:
    return _x(seconds), PAD_T + (1 - goals / top) * PLOT_H


def _x(seconds: float) -> float:
    minute = max(0.0, min(float(MATCH_MINUTES), seconds / 60.0))
    return PAD_L + minute / MATCH_MINUTES * PLOT_W


def _y(diff: int, peak: int, zero_y: float) -> float:
    return zero_y - diff / peak * (PLOT_H / 2 - 4)


def _poly(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def _elapsed(action: PlayAction) -> float | None:
    seconds = period_seconds(action.clock_raw)
    if seconds is None:
        text = (action.clock_raw or "").strip()
        if ":" not in text:
            return None
        minutes_text, seconds_text = text.split(":", 1)
        try:
            whole = int(minutes_text) * 60 + int(seconds_text)
        except ValueError:
            return None
        if whole < 0:
            return None
        return float(whole)
    return float(PERIOD_OFFSETS.get(action.period_code or "", 0) + seconds)
