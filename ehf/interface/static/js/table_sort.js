(() => {
  const EMPTY = new Set(["", "—", "-", "–"]);

  function cellText(cell) {
    return (cell?.innerText || "").replace(/\s+/g, " ").trim();
  }

  function parseEmpty(text) {
    return EMPTY.has(text) ? { empty: true } : null;
  }

  function parsePercent(text) {
    const match = text.match(/^([+-]?\d+(?:[.,]\d+)?)%$/);
    return match ? { n: Number(match[1].replace(",", ".")) } : null;
  }

  function parsePair(text) {
    const match = text.match(/^(\d+):(\d+)\b/);
    return match ? { n: Number(match[1]) * 1000 + Number(match[2]) } : null;
  }

  function parseNumber(text) {
    const compact = text.replace(/(\d)[\s\u00a0](?=\d{3}\b)/g, "$1");
    return /^-?\d+(?:[.,]\d+)?$/.test(compact) ? { n: Number(compact.replace(",", ".")) } : null;
  }

  function parseDate(text) {
    return /^\d{4}-\d{2}-\d{2}/.test(text) ? { n: Date.parse(text.slice(0, 10)) } : null;
  }

  function parseText(text) {
    return { s: text };
  }

  const parsers = [parseEmpty, parsePercent, parsePair, parseNumber, parseDate, parseText];

  function sortValue(text) {
    for (const parse of parsers) {
      const value = parse(text);
      if (value) return value;
    }
    return { s: text };
  }

  function compare(left, right, descending) {
    const a = sortValue(left);
    const b = sortValue(right);
    if (a.empty && b.empty) return 0;
    if (a.empty) return 1;
    if (b.empty) return -1;
    const result =
      a.n != null && b.n != null
        ? a.n - b.n
        : String(a.s ?? left).localeCompare(String(b.s ?? right), "en", { numeric: true });
    return descending ? -result : result;
  }

  class TableSort {
    prepare(root) {
      (root || document).querySelectorAll("table thead th").forEach((header) => {
        if (!header.textContent.trim()) return;
        header.classList.add("sortable");
        if (!header.hasAttribute("tabindex")) header.tabIndex = 0;
      });
    }

    remote(header) {
      const table = header.closest("table");
      const column = header.dataset.sort;
      if (!table?.hasAttribute("data-remote-sort") || !column) return false;
      const url = new URL(window.location.href);
      const sortKey = table.dataset.sortParam || "sort";
      const dirKey = table.dataset.dirParam || "dir";
      const pageKey = table.dataset.pageParam || "page";
      const current = url.searchParams.get(sortKey) || table.dataset.sortDefault || "";
      const currentDesc = url.searchParams.has(dirKey)
        ? url.searchParams.get(dirKey) === "desc"
        : table.dataset.sortDefaultDir === "desc" && current === (table.dataset.sortDefault || "");
      url.searchParams.set(sortKey, column);
      url.searchParams.set(dirKey, column === current && !currentDesc ? "desc" : "asc");
      url.searchParams.set(pageKey, "1");
      if (table.dataset.keepTab) url.searchParams.set("tab", table.dataset.keepTab);
      window.location.assign(url);
      return true;
    }

    toggle(header) {
      if (this.remote(header)) return;
      const table = header.closest("table");
      const body = table?.tBodies[0];
      const heads = table?.tHead && [...table.tHead.rows[0].cells];
      if (!body || !heads) return;
      const index = heads.indexOf(header);
      if (index < 0) return;
      const descending = header.getAttribute("aria-sort") === "ascending";
      heads.forEach((item) => item.removeAttribute("aria-sort"));
      header.setAttribute("aria-sort", descending ? "descending" : "ascending");
      const movable = [];
      const pinned = [];
      [...body.rows].forEach((row) => {
        (row.querySelector("td[colspan]") ? pinned : movable).push(row);
      });
      movable.sort((left, right) =>
        compare(cellText(left.cells[index]), cellText(right.cells[index]), descending),
      );
      movable.concat(pinned).forEach((row) => body.append(row));
    }

    start() {
      this.prepare(document);
      document.addEventListener("click", (event) => {
        const header = event.target.closest("thead th.sortable");
        if (header) this.toggle(header);
      });
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        const header = event.target.closest("thead th.sortable");
        if (!header) return;
        event.preventDefault();
        this.toggle(header);
      });
    }
  }

  const sorter = new TableSort();
  window.EhfTableSort = sorter;
  sorter.start();
})();
