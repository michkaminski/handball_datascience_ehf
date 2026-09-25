from __future__ import annotations

from flask import render_template
from flask.views import MethodView

from ehf.domain.errors import DataReadError
from ehf.domain.news import NewsPage
from ehf.interface.news_presenter import NewsPresenter
from ehf.interface.pages import STRONA_START
from ehf.services.news import NewsService


class StartView(MethodView):
    def __init__(self, service: NewsService) -> None:
        self._service = service
        self._presenter = NewsPresenter()

    def get(self) -> str:
        try:
            page = self._service.load_page()
            error = None
        except DataReadError as exc:
            page = NewsPage.empty()
            error = str(exc)
        aktualnosci = self._presenter.prepare(page)
        return render_template(
            "pages/start.html",
            strona=STRONA_START,
            sekcja_aktywna="start",
            aktualnosci=aktualnosci,
            error=error,
        )
