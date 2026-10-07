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
      const play = this.root.querySelector("[data-play]");
      this.play = play ? new PlayBoard(play) : null;
      this.play?.start();
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
        if (!panel.hidden && panel.dataset.src) this.load(panel);
      });
    }

    selectTab(name) {
      const index = this.buttons.findIndex((button) => button.dataset.tab === name);
      if (index >= 0) this.select(index);
    }

    // Panels with data-src (Statistics) are read from the server the first time they are opened.
    async load(panel) {
      if (panel.dataset.loaded) return;
      panel.dataset.loaded = "loading";
      const slot = panel.querySelector("[data-stats-slot]") || panel;
      try {
        const response = await fetch(panel.dataset.src, { headers: { "X-Requested-With": "fetch" } });
        if (!response.ok) throw new Error(String(response.status));
        slot.outerHTML = await response.text();
        panel.dataset.loaded = "yes";
        const stats = panel.querySelector("[data-stats]");
        if (stats) new StatsBoard(stats, this).start();
      } catch {
        delete panel.dataset.loaded;
        slot.innerHTML = '<p class="note">Could not load the statistics. Open the tab again to retry.</p>';
      }
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
      const row = this.events.find((item) => !item.hidden && Number(item.dataset.minute) >= minute);
      this.reveal(row);
    }

    reveal(row) {
      if (!this.list || !row) return;
      const head = this.list.querySelector(".pbp-list-head");
      const offset = (head ? head.offsetHeight : 0) + 34;
      this.list.scrollTo({ top: row.offsetTop - offset, behavior: "smooth" });
      this.list.scrollIntoView({ behavior: "smooth", block: "nearest" });
      row.classList.remove("is-jump");
      void row.offsetWidth;
      row.classList.add("is-jump");
    }

    // Opened from the Statistics tab: show everything, highlight the player, scroll to the first event.
    follow(person) {
      this.selectFilter("all");
      this.person = person;
      this.apply();
      this.reveal(this.events.find((row) => row.classList.contains("is-hit")));
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

  class StatsBoard {
    constructor(root, tabs) {
      this.root = root;
      this.tabs = tabs;
    }

    start() {
      this.views = Array.from(this.root.querySelectorAll("[data-stats-tab]"));
      this.views.forEach((button, index) => {
        button.addEventListener("click", () => this.show(button.dataset.statsTab));
        button.addEventListener("keydown", (event) => {
          const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
          if (!step) return;
          event.preventDefault();
          const next = this.views[(index + step + this.views.length) % this.views.length];
          this.show(next.dataset.statsTab);
          next.focus();
        });
      });
      this.root.addEventListener("click", (event) => {
        const show = event.target.closest("[data-show-in-play]");
        if (show) {
          this.showInPlay(show.dataset.showInPlay);
          return;
        }
        if (event.target.closest("[data-pop-close]")) {
          this.closePop();
          return;
        }
        const zone = event.target.closest("[data-zone]");
        if (zone) {
          this.openPop(zone);
          return;
        }
        if (this.pop && !event.target.closest(".mst-pop")) this.closePop();
        const row = event.target.closest("[data-player]");
        if (row) this.toggle(row);
      });
      this.root.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && this.pop) {
          this.closePop();
          return;
        }
        const target = event.target.closest("[data-player], [data-zone]");
        if (!target || (event.key !== "Enter" && event.key !== " ")) return;
        event.preventDefault();
        if (target.dataset.zone) this.openPop(target);
        else this.toggle(target);
      });
    }

    // Shooting: a small window with the players who shot from the clicked zone (court spot or table row).
    openPop(trigger) {
      const name = trigger.dataset.zone;
      const card = trigger.closest("[data-zone-card]");
      const pop = card ? card.querySelector('[data-zone-pop="' + name + '"]') : null;
      if (!pop) return;
      const same = this.pop === pop;
      this.closePop();
      if (same) return;
      const box = card.getBoundingClientRect();
      const at = trigger.getBoundingClientRect();
      pop.hidden = false;
      const width = pop.offsetWidth;
      const left = Math.min(Math.max(at.left - box.left + at.width / 2 - width / 2, 12), box.width - width - 12);
      pop.style.left = left + "px";
      pop.style.top = at.bottom - box.top + 6 + "px";
      card.querySelectorAll('tr[data-zone="' + name + '"]').forEach((row) => row.classList.add("is-open"));
      this.pop = pop;
    }

    closePop() {
      if (!this.pop) return;
      this.pop.hidden = true;
      const card = this.pop.closest("[data-zone-card]");
      if (card) card.querySelectorAll("tr.is-open").forEach((row) => row.classList.remove("is-open"));
      this.pop = null;
    }

    show(name) {
      this.closePop();
      this.views.forEach((button) => {
        const active = button.dataset.statsTab === name;
        button.setAttribute("aria-selected", String(active));
        button.tabIndex = active ? 0 : -1;
      });
      this.root.querySelectorAll("[data-stats-panel]").forEach((panel) => {
        panel.hidden = panel.dataset.statsPanel !== name;
      });
    }

    toggle(row) {
      const detail = this.root.querySelector(`[data-player-detail="${row.dataset.player}"]`);
      if (!detail) return;
      const open = detail.hidden;
      detail.hidden = !open;
      row.setAttribute("aria-expanded", String(open));
      row.classList.toggle("is-open", open);
    }

    showInPlay(person) {
      if (!this.tabs?.play) return;
      this.tabs.selectTab("play");
      this.tabs.play.follow(person);
    }
  }

  const page = document.querySelector("[data-match-detail]");
  if (page) new MatchTabs(page).start();
})();
