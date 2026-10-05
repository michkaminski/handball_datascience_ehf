(() => {
  const DOUBLE_CLICK_MS = 250;

  class DetailDialog {
    constructor(dialog, load) {
      this.dialog = dialog;
      this.load = load;
      this.body = dialog.querySelector("[data-detail-content]");
      this.request = null;
      this.origin = null;
    }

    start() {
      this.dialog.querySelectorAll("[data-detail-close]").forEach((button) => {
        button.addEventListener("click", () => this.dialog.close());
      });
      this.dialog.addEventListener("close", () => {
        this.request?.abort();
        this.body.replaceChildren();
        this.origin?.focus();
        this.origin = null;
      });
    }

    async open(href, origin) {
      this.request?.abort();
      const request = new AbortController();
      this.request = request;
      if (!this.dialog.open) this.origin = origin;
      this.body.textContent = "Loading details…";
      this.body.setAttribute("aria-busy", "true");
      this.dialog.querySelector("[data-detail-tab]").href = href;
      if (!this.dialog.open) this.dialog.showModal();
      try {
        const response = await this.load(href, { signal: request.signal });
        if (!response.ok) throw new Error("failed");
        const documentTree = new DOMParser().parseFromString(await response.text(), "text/html");
        const detail = documentTree.querySelector("[data-match-detail]");
        if (!detail) throw new Error("missing");
        detail.querySelector("[data-detail-navigation]")?.remove();
        if (!request.signal.aborted) {
          this.body.replaceChildren(detail);
          this.body.scrollTop = 0;
          if (window.EhfMatchTabs) new window.EhfMatchTabs(detail).start();
          window.EhfTableSort?.prepare(detail);
        }
      } catch {
        if (!request.signal.aborted) {
          this.body.textContent = "Could not load details. Close the window and try again, or open them in a new tab.";
        }
      } finally {
        if (this.request === request) this.body.removeAttribute("aria-busy");
      }
    }
  }

  // Rows: double-click or Enter opens the modal.
  function bindRows(table, detailDialog) {
    table.querySelectorAll("tbody tr[data-href]").forEach((row) => {
      row.classList.add("row-clickable");
      row.tabIndex = 0;
      row.addEventListener("dblclick", (event) => {
        if (!event.target.closest("a, button, input, select")) detailDialog.open(row.dataset.href, row);
      });
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && event.target === row) {
          event.preventDefault();
          detailDialog.open(row.dataset.href, row);
        }
      });
    });
  }

  // Links: single click opens the modal, double click opens a new tab.
  // Modifier and middle clicks keep the browser default.
  function bindLinks(detailDialog) {
    let pending = null;
    document.addEventListener("click", (event) => {
      const link = event.target.closest("a[data-detail-link]");
      if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      clearTimeout(pending);
      if (event.detail === 0) {
        detailDialog.open(link.href, link);
        return;
      }
      if (event.detail > 1) return;
      pending = setTimeout(() => detailDialog.open(link.href, link), DOUBLE_CLICK_MS);
    });
    document.addEventListener("dblclick", (event) => {
      const link = event.target.closest("a[data-detail-link]");
      if (!link) return;
      event.preventDefault();
      clearTimeout(pending);
      window.open(link.href, "_blank", "noopener");
    });
  }

  const dialog = document.getElementById("match-detail-dialog");
  if (!dialog || typeof dialog.showModal !== "function") return;
  const detailDialog = new DetailDialog(dialog, window.fetch.bind(window));
  detailDialog.start();
  bindLinks(detailDialog);
  const tables = new Set(
    [...document.querySelectorAll("[data-match-rows]"), document.getElementById("matches-table")].filter(Boolean)
  );
  tables.forEach((table) => bindRows(table, detailDialog));
})();
