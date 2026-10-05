(() => {
  // Changing season or competition reloads the team list.
  const scope = document.querySelector("[data-sheet-scope]");
  scope?.querySelectorAll("select").forEach((select) => select.addEventListener("change", () => scope.submit()));

  const form = document.querySelector("[data-sheet-form]");
  const warning = document.querySelector("[data-sheet-same]");
  form?.addEventListener("submit", (event) => {
    const same = form.home_id.value && form.home_id.value === form.away_id.value;
    warning.hidden = !same;
    if (same) event.preventDefault();
  });
})();
