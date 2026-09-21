from __future__ import annotations

from flask import Blueprint, render_template
from flask.views import MethodView

from ehf.interface.pages import STRONY, Strona


class SzkieletView(MethodView):
    def __init__(self, strona: Strona) -> None:
        self._strona = strona

    def get(self, identyfikator: int | None = None) -> str:
        return render_template(
            f"pages/{self._strona.wzor}.html",
            strona=self._strona,
            sekcja_aktywna=self._strona.klucz,
            identyfikator=identyfikator,
        )


def utworz_blueprint() -> Blueprint:
    blueprint = Blueprint("panel", __name__)
    for strona in STRONY:
        if not strona.uses_skeleton:
            continue
        blueprint.add_url_rule(
            strona.sciezka,
            view_func=SzkieletView.as_view(strona.endpoint, strona=strona),
        )
    return blueprint
