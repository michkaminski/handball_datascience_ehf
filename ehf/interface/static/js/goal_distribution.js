(function () {
  const root = document.querySelector("[data-goal-distribution]");
  if (!root) return;
  const dialog = root.querySelector("[data-goal-dialog]");
  const body = root.querySelector("[data-goal-body]");
  const title = root.querySelector("[data-goal-title]");
  const form = document.getElementById("goal-dist-filters");
  const base = root.dataset.matchesUrl;
  if (!dialog || !body || !title || !form || !base) return;

  root.querySelectorAll("[data-goal-close]").forEach((button) => {
    button.addEventListener("click", () => dialog.close());
  });

  root.querySelectorAll("[data-goal-bar]").forEach((bar) => {
    bar.addEventListener("click", async () => {
      const params = new URLSearchParams(new FormData(form));
      params.set("series", bar.dataset.series);
      params.set("goals", bar.dataset.goals);
      title.textContent = bar.dataset.caption || "Matches";
      body.innerHTML = '<p class="note">Loading…</p>';
      if (!dialog.open) dialog.showModal();
      try {
        const response = await fetch(`${base}?${params.toString()}`, {
          headers: { Accept: "text/html" },
        });
        if (!response.ok) throw new Error(String(response.status));
        body.innerHTML = await response.text();
      } catch (_error) {
        body.innerHTML = '<p class="note">Could not load matches.</p>';
      }
    });
  });
})();
