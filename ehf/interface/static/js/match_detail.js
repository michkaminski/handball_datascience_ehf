(() => {
  class MatchTabs {
    constructor(root) {
      this.root = root;
      this.bar = root.querySelector("[data-match-tabs]");
    }

    start() {
      if (!this.bar) return;
      this.buttons = Array.from(this.bar.querySelectorAll("[role=tab]"));
      this.panels = Array.from(this.root.querySelectorAll("[data-match-panel]"));
      this.panels.forEach((panel) => {
        panel.setAttribute("role", "tabpanel");
        panel.tabIndex = 0;
      });
      this.bar.hidden = false;
      this.buttons.forEach((button, index) => {
        button.addEventListener("click", () => this.select(index));
        button.addEventListener("keydown", (event) => {
          const next = {
            ArrowRight: (index + 1) % this.buttons.length,
            ArrowLeft: (index + this.buttons.length - 1) % this.buttons.length,
            Home: 0,
            End: this.buttons.length - 1,
          };
          if (!(event.key in next)) return;
          event.preventDefault();
          this.select(next[event.key]);
          this.buttons[next[event.key]].focus();
        });
      });
      this.select(0);
    }

    select(index) {
      this.buttons.forEach((button, number) => {
        button.setAttribute("aria-selected", String(number === index));
        button.tabIndex = number === index ? 0 : -1;
      });
      const id = this.buttons[index].getAttribute("aria-controls");
      this.panels.forEach((panel) => {
        panel.hidden = panel.id !== id;
      });
    }
  }

  const page = document.querySelector("[data-match-detail]");
  if (page) new MatchTabs(page).start();
})();
