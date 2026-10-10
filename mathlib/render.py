from __future__ import annotations

import html
import re
from dataclasses import dataclass

from mathlib.registry import BibEntry, Concept, MathRegistry

_CONCEPT_LINK = re.compile(r"<a\s+([^>]*?)data-concept=\"([^\"]+)\"([^>]*)>")
_ANCHOR_ATTR = re.compile(r"data-anchor=\"([^\"]+)\"")
_BIB_ITEM = re.compile(r"<li([^>]*)data-bib=\"([^\"]+)\"([^>]*)>\s*</li>")
_CITE = re.compile(r"<cite\s+data-bib=\"([^\"]+)\"\s*>\s*</cite>")
_H2 = re.compile(r"<section\s+id=\"([^\"]+)\"\s*>\s*<h2>(.*?)</h2>", re.DOTALL)
_H3 = re.compile(r"<h3\s+id=\"([^\"]+)\"\s*>(.*?)</h3>", re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class TocEntry:
    id: str
    title: str
    level: int
    number: str


@dataclass(frozen=True)
class RenderedArticle:
    concept: Concept
    html: str
    toc: tuple[TocEntry, ...]
    bibliography: tuple[BibEntry, ...]


def format_bibliography(entry: BibEntry) -> str:
    data = entry.data
    parts = [f"{html.escape(str(data.get('authors', '')))} ({data.get('year', '')})."]
    title = html.escape(str(data.get("title", "")))
    if data.get("type") in {"book", "web"}:
        parts.append(f"<i>{title}</i>.")
    else:
        parts.append(f"{title}.")
    venue = data.get("journal")
    if venue:
        volume = data.get("volume")
        issue = data.get("issue")
        pages = data.get("pages")
        detail = f"<i>{html.escape(str(venue))}</i>"
        if volume:
            detail += f", {html.escape(str(volume))}"
            if issue:
                detail += f"({html.escape(str(issue))})"
        if pages:
            detail += f", {html.escape(str(pages))}"
        parts.append(detail + ".")
    for field in ("edition", "publisher"):
        if data.get(field):
            parts.append(f"{html.escape(str(data[field]))}.")
    doi = data.get("doi")
    if doi:
        parts.append(
            f'DOI: <a href="https://doi.org/{html.escape(str(doi))}" rel="noopener">'
            f"{html.escape(str(doi))}</a>"
        )
    elif data.get("url"):
        url = html.escape(str(data["url"]))
        parts.append(f'<a href="{url}" rel="noopener">{url}</a>')
    return " ".join(parts)


class ArticleRenderer:
    def __init__(self, registry: MathRegistry) -> None:
        self._registry = registry

    def render(self, concept: Concept) -> RenderedArticle:
        registry = self._registry
        source = registry.article_html(concept)
        cited: list[str] = []

        def concept_link(match: re.Match[str]) -> str:
            before, target, after = match.group(1), match.group(2), match.group(3)
            attributes = before + after
            anchor_match = _ANCHOR_ATTR.search(attributes)
            anchor = anchor_match.group(1) if anchor_match else None
            linked = registry.concepts.get(target)
            if linked is None:
                return match.group(0)
            url = registry.url(target, anchor)
            summary = html.escape(linked.summary, quote=True)
            return (
                f'<a {before}data-concept="{target}"{after} href="{url}" '
                f'class="ml-concept" title="{summary}">'
            )

        def bib_item(match: re.Match[str]) -> str:
            key = match.group(2)
            entry = registry.bibliography.get(key)
            if entry is None:
                return match.group(0)
            cited.append(key)
            return f'<li id="bib-{key}" data-bib="{key}">{format_bibliography(entry)}</li>'

        def cite(match: re.Match[str]) -> str:
            key = match.group(1)
            entry = registry.bibliography.get(key)
            if entry is None:
                return match.group(0)
            label = html.escape(entry.citation())
            return f'<cite data-bib="{key}"><a href="#bib-{key}">({label})</a></cite>'

        rendered = _CONCEPT_LINK.sub(concept_link, source)
        rendered = _BIB_ITEM.sub(bib_item, rendered)
        rendered = _CITE.sub(cite, rendered)
        toc: list[TocEntry] = []
        counter = {"section": 0, "sub": 0}

        def numbered_section(match: re.Match[str]) -> str:
            counter["section"] += 1
            counter["sub"] = 0
            number = str(counter["section"])
            title = match.group(2).strip()
            toc.append(TocEntry(match.group(1), _TAGS.sub("", title), 2, number))
            return (
                f'<section id="{match.group(1)}"><h2><a class="ml-anchor" href="#{match.group(1)}">'
                f"{number}.</a> {title}</h2>"
            )

        rendered = _H2.sub(numbered_section, rendered)
        for match in _H3.finditer(rendered):
            toc.append(TocEntry(match.group(1), _TAGS.sub("", match.group(2)).strip(), 3, ""))
        ordered = self._order_toc(rendered, toc)
        return RenderedArticle(
            concept=concept,
            html=rendered,
            toc=tuple(ordered),
            bibliography=tuple(registry.bibliography[key] for key in dict.fromkeys(cited)),
        )

    def _order_toc(self, rendered: str, toc: list[TocEntry]) -> list[TocEntry]:
        positions = {entry.id: rendered.find(f'id="{entry.id}"') for entry in toc}
        return sorted(toc, key=lambda entry: positions[entry.id])
