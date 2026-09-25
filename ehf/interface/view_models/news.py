from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeczAktualnosciViewModel:
    id: int
    day: str
    time: str
    home: str
    away: str
    score: str
    winner: str | None
    competition: str | None = None
    stage: str | None = None


@dataclass(frozen=True)
class StrzelecAktualnosciViewModel:
    pozycja: int
    id_zawodnik: int
    zawodnik: str
    druzyna: str
    mecze: int
    bramki: int
    srednia: str


@dataclass(frozen=True)
class BramkarzAktualnosciViewModel:
    pozycja: int
    id_zawodnik: int
    zawodnik: str
    druzyna: str
    mecze: int
    rzuty: int
    obrony: int
    skutecznosc: str


@dataclass(frozen=True)
class SekcjaAktualnosciViewModel:
    klucz: str
    etykieta: str
    rozgrywki: str
    id_rozgrywek: int
    liczba_rozegranych: int
    srednia_bramek: str
    mecze: list[MeczAktualnosciViewModel]
    strzelcy: list[StrzelecAktualnosciViewModel]
    bramkarze: list[BramkarzAktualnosciViewModel]


@dataclass(frozen=True)
class CiekawostkaViewModel:
    tytul: str
    wartosc: str
    opis: str
    id_mecz: int | None = None
    id_zawodnik: int | None = None


@dataclass(frozen=True)
class NadchodzacaSekcjaViewModel:
    klucz: str
    rozgrywki: str
    id_rozgrywek: int
    mecze: list[MeczAktualnosciViewModel]


@dataclass(frozen=True)
class AktualnosciViewModel:
    sezon: str | None
    id_sezon: int | None
    stan_danych: str
    liczba_rozegranych: int
    suma_bramek: int
    sekcje: list[SekcjaAktualnosciViewModel]
    ciekawostki: list[CiekawostkaViewModel]
    nadchodzace_sekcje: list[NadchodzacaSekcjaViewModel]
