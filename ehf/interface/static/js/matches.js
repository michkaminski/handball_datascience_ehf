(() => {
  class MatchDetailDialog {
    constructor(table, dialog, load) {
      this.table = table;
      this.dialog = dialog;
      this.load = load;
      this.body = dialog.querySelector("[data-detail-content]");
      this.request = null;
      this.row = null;
    }

    start() {
      this.dialog.querySelectorAll("[data-detail-close]").forEach((button) => {
        button.addEventListener("click", () => this.dialog.close());
      });
      this.dialog.addEventListener("close", () => {
        this.request?.abort();
        this.body.replaceChildren();
        this.row?.focus();
      });
      this.table.querySelectorAll("tbody tr[data-href]").forEach((row) => {
        row.classList.add("row-clickable");
        row.tabIndex = 0;
        row.addEventListener("dblclick", (event) => {
          if (!event.target.closest("a, button, input, select")) this.open(row);
        });
        row.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && event.target === row) {
            event.preventDefault();
            this.open(row);
          }
        });
      });
    }

    async open(row) {
      this.request?.abort();
      const request = new AbortController();
      this.request = request;
      this.row = row;
      this.body.textContent = "Loading match details…";
      this.body.setAttribute("aria-busy", "true");
      this.dialog.querySelector("[data-detail-tab]").href = row.dataset.href;
      if (!this.dialog.open) this.dialog.showModal();
      try {
        const response = await this.load(row.dataset.href, { signal: request.signal });
        if (!response.ok) throw new Error("failed");
        const documentTree = new DOMParser().parseFromString(await response.text(), "text/html");
        const detail = documentTree.querySelector("[data-match-detail]");
        if (!detail) throw new Error("missing");
        detail.querySelector("[data-detail-navigation]")?.remove();
        if (!request.signal.aborted) {
          this.body.replaceChildren(detail);
          if (window.EhfMatchTabs) new window.EhfMatchTabs(detail).start();
          window.EhfTableSort?.prepare(detail);
        }
      } catch {
        if (!request.signal.aborted) {
          this.body.textContent = "Could not load match details. Close the window and try again, or open the match in a new tab.";
        }
      } finally {
        if (this.request === request) this.body.removeAttribute("aria-busy");
      }
    }
  }

  const table = document.getElementById("matches-table");
  const dialog = document.getElementById("match-detail-dialog");
  if (table && dialog && typeof dialog.showModal === "function") {
    new MatchDetailDialog(table, dialog, window.fetch.bind(window)).start();
  }
})();
