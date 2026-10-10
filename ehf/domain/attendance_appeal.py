from __future__ import annotations

from dataclasses import dataclass

from maf.records import Measure, ModelSpec


@dataclass(frozen=True)
class AppealModel:
    spec: ModelSpec
    gender: str


APPEAL_MODELS: tuple[AppealModel, ...] = (
    AppealModel(
        ModelSpec(
            "men-count",
            "Men — spectators",
            Measure.COUNT,
            "EHF club competitions, men; all played matches with known attendance",
        ),
        "men",
    ),
    AppealModel(
        ModelSpec(
            "women-count",
            "Women — spectators",
            Measure.COUNT,
            "EHF club competitions, women; all played matches with known attendance",
            reference_seasons=2,
        ),
        "women",
    ),
)


def appeal_model(key: str | None) -> AppealModel:
    for model in APPEAL_MODELS:
        if model.spec.key == key:
            return model
    return APPEAL_MODELS[0]


METRIC_CONCEPTS: dict[str, tuple[str, str | None]] = {
    "suma": ("srednia-arytmetyczna", "definicja"),
    "srednia": ("srednia-arytmetyczna", "wzor"),
    "mediana": ("mediana", "definicja"),
    "odchylenie": ("odchylenie-standardowe", "wzor"),
    "wypelnienie": ("rozklad-beta", "definicja"),
    "mecze": ("partial-pooling", "wzor"),
    "rekord": ("percentyle", "definicja"),
    "efekt_rywala": ("interpretacja-wspolczynnikow", None),
    "iaf": ("atrakcyjnosc-frekwencyjna", "wzor"),
    "iaf_posterior": ("rozklad-posterior", "definicja"),
    "przedzial": ("przedzial-wiarygodnosci", "wzor"),
    "p_iaf": ("probabilistyczne-porownanie-parametrow", "wzor"),
    "efekt_pp": ("interpretacja-wspolczynnikow", "wzor"),
    "hierarchia": ("modele-hierarchiczne", "definicja"),
    "pooling": ("partial-pooling", "wzor"),
    "efekty_losowe": ("efekty-stale-i-losowe", "definicja"),
    "identyfikowalnosc": ("identyfikowalnosc-parametrow", "definicja"),
    "logit": ("funkcja-logit", "wzor"),
    "beta_dwumianowy": ("rozklad-beta-dwumianowy", "wzor"),
    "ujemny_dwumianowy": ("rozklad-ujemny-dwumianowy", "wzor"),
    "bayes": ("twierdzenie-bayesa", "wzor"),
    "prior": ("priory", "definicja"),
    "hiperprior": ("hiperpriory", "definicja"),
    "mcmc": ("mcmc", "definicja"),
    "monte_carlo": ("monte-carlo", "definicja"),
    "predykcja": ("rozklad-predykcyjny", "wzor"),
    "przedzial_predykcyjny": ("przedzialy-predykcyjne", "definicja"),
    "niepewnosc": ("niepewnosc-predykcyjna", "wzor"),
    "wartosc_oczekiwana_prognozy": ("wartosc-oczekiwana-prognozy", "wzor"),
    "z_score": ("z-score", None),
    "reszty": ("diagnostyka-reszt", "definicja"),
    "rhat": ("r-hat", "wzor"),
    "ess": ("effective-sample-size", "wzor"),
    "ppc": ("posterior-predictive-checks", "definicja"),
    "mae": ("mae", "wzor"),
    "rmse": ("rmse", "wzor"),
    "pokrycie": ("pokrycie-przedzialow-predykcyjnych", "wzor"),
    "kalibracja": ("kalibracja-prawdopodobienstw", "definicja"),
    "backtest": ("backtesting", "definicja"),
    "forma": ("srednia-ruchoma", "wzor"),
    "standaryzacja": ("standaryzacja", "wzor"),
    "wspolczynniki": ("interpretacja-wspolczynnikow", "definicja"),
    "trend": ("regresja-hierarchiczna", "definicja"),
}
