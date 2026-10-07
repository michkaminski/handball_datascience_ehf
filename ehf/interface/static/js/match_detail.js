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
      const wanted = new URLSearchParams(window.location.search).get("tab");
      const index = this.buttons.findIndex((button) => button.dataset.tab === wanted);
      this.select(index >= 0 ? index : 0);
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

  window.EhfMatchTabs = MatchTabs;

  class PlayBoard {
    constructor(root) {
      this.root = root;
      this.filter = "all";
      this.person = "";
    }

    start() {
      this.events = Array.from(this.root.querySelectorAll("[data-play-filter]"));
      this.structure = Array.from(this.root.querySelectorAll("[data-play-structure]"));
      this.root.querySelectorAll("[data-play-filter-btn]").forEach((button) => {
        button.addEventListener("click", () => this.selectFilter(button.dataset.playFilterBtn));
      });
      this.list = this.root.querySelector("[data-play-list]");
      this.root.addEventListener("click", (event) => {
        const bar = event.target.closest("[data-jump-minute]");
        if (bar) {
          this.jump(Number(bar.dataset.jumpMinute));
          return;
        }
        const person = event.target.closest("[data-play-person]");
        if (!person) return;
        this.selectPerson(person.dataset.playPerson || "");
      });
      this.root.addEventListener("keydown", (event) => {
        const bar = event.target.closest("[data-jump-minute]");
        if (!bar || (event.key !== "Enter" && event.key !== " ")) return;
        event.preventDefault();
        this.jump(Number(bar.dataset.jumpMinute));
      });
    }

    // Scroll the event list to the first visible event of the clicked minute (or the next one with events).
    jump(minute) {
      if (!this.list) return;
      const row = this.events.find((item) => !item.hidden && Number(item.dataset.minute) >= minute);
      if (!row) return;
      const head = this.list.querySelector(".pbp-list-head");
      const offset = (head ? head.offsetHeight : 0) + 34;
      this.list.scrollTo({ top: row.offsetTop - offset, behavior: "smooth" });
      this.list.scrollIntoView({ behavior: "smooth", block: "nearest" });
      row.classList.remove("is-jump");
      void row.offsetWidth;
      row.classList.add("is-jump");
    }

    selectFilter(filter) {
      this.filter = filter || "all";
      this.root.querySelectorAll("[data-play-filter-btn]").forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.playFilterBtn === this.filter));
      });
      this.apply();
    }

    selectPerson(person) {
      this.person = this.person === person ? "" : person;
      this.apply();
    }

    apply() {
      const person = this.person;
      this.events.forEach((row) => {
        const shown = this.filter === "all" || row.dataset.playFilter === this.filter;
        row.hidden = !shown;
        const ids = (row.dataset.playPeople || "").split(",").filter(Boolean);
        const hit = shown && Boolean(person) && ids.includes(person);
        row.classList.toggle("is-hit", hit);
        row.classList.toggle("is-dim", shown && Boolean(person) && !hit);
      });
      this.root.querySelectorAll("[data-play-person]").forEach((node) => {
        node.classList.toggle("is-hit", Boolean(person) && node.dataset.playPerson === person);
      });
      this.structure.forEach((row) => {
        row.hidden = this.filter !== "all";
      });
    }
  }

  const page = document.querySelector("[data-match-detail]");
  if (page) new MatchTabs(page).start();
  const play = document.querySelector("[data-play]");
  if (play) new PlayBoard(play).start();
})();
