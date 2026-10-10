(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const MARGIN = { top: 16, right: 16, bottom: 34, left: 60 };
  const WIDE = { width: 960, height: 260 };
  const SMALL = { width: 480, height: 230 };

  function formatNumber(value) {
    return Math.round(value).toLocaleString("en-US").replace(/,/g, " ");
  }

  function compactNumber(value) {
    return value >= 10000 ? `${Math.round(value / 1000)}k` : value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(Math.round(value));
  }

  function element(name, attributes, text) {
    const node = document.createElementNS(SVG_NS, name);
    Object.entries(attributes || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  function niceMaximum(value) {
    if (value <= 0) return 1;
    const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
    const scaled = value / magnitude;
    const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10;
    return step * magnitude;
  }

  function showMessage(host, text) {
    host.textContent = text;
    host.classList.add("note");
  }

  function finish(host, svg, legendText) {
    host.classList.remove("note");
    host.replaceChildren(svg);
    if (!legendText) return;
    const legend = document.createElement("p");
    legend.className = "att-legend";
    legend.textContent = legendText;
    host.append(legend);
  }

  function newSvg(size, extraClass) {
    return element("svg", {
      viewBox: `0 0 ${size.width} ${size.height}`,
      class: extraClass ? `att-svg ${extraClass}` : "att-svg",
      preserveAspectRatio: "xMidYMid meet",
    });
  }

  function drawYAxis(svg, size, top, format) {
    const y = (value) => MARGIN.top + (size.height - MARGIN.top - MARGIN.bottom) * (1 - value / top);
    for (let step = 0; step <= 4; step += 1) {
      const value = (top / 4) * step;
      svg.append(
        element("line", { x1: MARGIN.left, x2: size.width - MARGIN.right, y1: y(value), y2: y(value), class: "att-grid" }),
        element("text", { x: MARGIN.left - 8, y: y(value) + 3, class: "att-axis att-axis-y" }, format(value)),
      );
    }
    return y;
  }

  function renderTrend(host, payload) {
    const points = payload.points || [];
    const values = points.flatMap((point) => [point.mean, point.q3, point.movingAverage]).filter((v) => v != null);
    if (!values.length) return showMessage(host, "No known attendance to chart.");
    const size = WIDE;
    const top = niceMaximum(Math.max(...values));
    const slot = (size.width - MARGIN.left - MARGIN.right) / points.length;
    const barWidth = Math.min(48, slot * 0.6);
    const x = (index) => MARGIN.left + slot * index + slot / 2;
    const svg = newSvg(size);
    const y = drawYAxis(svg, size, top, formatNumber);
    const labelEvery = Math.max(1, Math.ceil(points.length / 14));
    points.forEach((point, index) => {
      const group = element("g", { class: point.selected ? "att-bar att-bar-selected" : "att-bar" });
      const known = point.mean != null;
      const tip = known
        ? `${point.season}: mean ${formatNumber(point.mean)}, median ${formatNumber(point.median)}, ${point.known} of ${point.played} matches known`
        : `${point.season}: no known attendance (${point.played} played)`;
      group.append(element("title", {}, tip));
      if (known) {
        const barTop = y(point.mean);
        group.append(element("rect", { x: x(index) - barWidth / 2, y: barTop, width: barWidth, height: y(0) - barTop, rx: 2 }));
        if (point.q1 != null && point.q3 != null) {
          group.append(
            element("line", { x1: x(index), x2: x(index), y1: y(point.q1), y2: y(point.q3), class: "att-iqr" }),
            element("line", { x1: x(index) - 5, x2: x(index) + 5, y1: y(point.q1), y2: y(point.q1), class: "att-iqr" }),
            element("line", { x1: x(index) - 5, x2: x(index) + 5, y1: y(point.q3), y2: y(point.q3), class: "att-iqr" }),
          );
        }
      }
      svg.append(group);
      if (index % labelEvery === 0 || index === points.length - 1) {
        svg.append(element("text", { x: x(index), y: size.height - 12, class: "att-axis att-axis-x" }, point.season));
      }
    });
    const line = points
      .map((point, index) => (point.movingAverage == null ? null : `${x(index)},${y(point.movingAverage)}`))
      .filter(Boolean);
    if (line.length > 1) svg.append(element("polyline", { points: line.join(" "), class: "att-line" }));
    finish(host, svg, "Bars: mean attendance. Whiskers: Q1–Q3. Line: 3-season moving average.");
  }

  function renderCoverage(host, rows) {
    if (!rows.length) return showMessage(host, "No seasons to chart.");
    const size = WIDE;
    const margin = { ...MARGIN, right: 48 };
    const top = niceMaximum(Math.max(...rows.map((row) => row.known), 1));
    const innerHeight = size.height - margin.top - margin.bottom;
    const slot = (size.width - margin.left - margin.right) / rows.length;
    const barWidth = Math.min(48, slot * 0.6);
    const x = (index) => margin.left + slot * index + slot / 2;
    const yBars = (value) => margin.top + innerHeight * (1 - value / top);
    const yShare = (value) => margin.top + innerHeight * (1 - value / 100);
    const svg = newSvg(size);
    for (let step = 0; step <= 4; step += 1) {
      const value = (top / 4) * step;
      svg.append(
        element("line", { x1: margin.left, x2: size.width - margin.right, y1: yBars(value), y2: yBars(value), class: "att-grid" }),
        element("text", { x: margin.left - 8, y: yBars(value) + 3, class: "att-axis att-axis-y" }, formatNumber(value)),
        element("text", { x: size.width - margin.right + 8, y: yShare(25 * step) + 3, class: "att-axis att-axis-start" }, `${25 * step}%`),
      );
    }
    const labelEvery = Math.max(1, Math.ceil(rows.length / 14));
    const dots = [];
    rows.forEach((row, index) => {
      const group = element("g", { class: "att-bar" });
      const share = row.coverage == null ? "n/a" : `${row.coverage}%`;
      group.append(
        element("title", {}, `${row.season}: ${row.known} of ${row.played} matches with attendance (${share})`),
        element("rect", { x: x(index) - barWidth / 2, y: yBars(row.known), width: barWidth, height: yBars(0) - yBars(row.known), rx: 2 }),
      );
      svg.append(group);
      if (row.coverage != null) dots.push([x(index), yShare(row.coverage)]);
      if (index % labelEvery === 0 || index === rows.length - 1) {
        svg.append(element("text", { x: x(index), y: size.height - 12, class: "att-axis att-axis-x" }, row.season));
      }
    });
    if (dots.length > 1) svg.append(element("polyline", { points: dots.map((dot) => dot.join(",")).join(" "), class: "att-line" }));
    dots.forEach(([cx, cy]) => svg.append(element("circle", { cx, cy, r: 3, class: "att-line-dot" })));
    finish(host, svg, "Bars: matches with known attendance (left axis). Line: coverage % of played matches (right axis).");
  }

  function renderColumns(host, items, options) {
    const usable = items.filter((item) => item.value != null);
    if (!usable.length) return showMessage(host, options.empty || "No known attendance to chart.");
    const size = options.size || SMALL;
    const top = niceMaximum(Math.max(...usable.map((item) => item.value)));
    const slot = (size.width - MARGIN.left - MARGIN.right) / items.length;
    const barWidth = Math.min(44, slot * 0.7);
    const x = (index) => MARGIN.left + slot * index + slot / 2;
    const svg = newSvg(size);
    const y = drawYAxis(svg, size, top, options.format || formatNumber);
    const labelEvery = Math.max(1, Math.ceil(items.length / Math.floor((size.width - MARGIN.left - MARGIN.right) / (options.labelWidth || 44))));
    items.forEach((item, index) => {
      if (item.value != null) {
        const group = element("g", { class: "att-bar" });
        group.append(
          element("title", {}, item.tip),
          element("rect", { x: x(index) - barWidth / 2, y: y(item.value), width: barWidth, height: y(0) - y(item.value), rx: 2 }),
        );
        svg.append(group);
      }
      if (index % labelEvery === 0) {
        svg.append(element("text", { x: x(index), y: size.height - 12, class: "att-axis att-axis-x" }, item.label));
      }
    });
    finish(host, svg, options.legend);
  }

  function renderRows(host, items, options) {
    const usable = items.filter((item) => item.value != null);
    if (!usable.length) return showMessage(host, options.empty || "No known attendance to chart.");
    const rowHeight = 22;
    const left = 170;
    const right = 56;
    const width = 960;
    const height = 12 + rowHeight * usable.length + 28;
    const top = niceMaximum(Math.max(...usable.map((item) => item.value)));
    const scale = (value) => ((width - left - right) * value) / top;
    const svg = newSvg({ width, height });
    for (let step = 0; step <= 4; step += 1) {
      const value = (top / 4) * step;
      const gx = left + scale(value);
      svg.append(
        element("line", { x1: gx, x2: gx, y1: 6, y2: height - 24, class: "att-grid" }),
        element("text", { x: gx, y: height - 8, class: "att-axis att-axis-x" }, formatNumber(value)),
      );
    }
    usable.forEach((item, index) => {
      const rowTop = 10 + rowHeight * index;
      const group = element("g", { class: "att-bar" });
      group.append(
        element("title", {}, item.tip),
        element("rect", { x: left, y: rowTop, width: Math.max(scale(item.value), 1), height: rowHeight - 6, rx: 2 }),
      );
      svg.append(
        element("text", { x: left - 8, y: rowTop + 11, class: "att-axis att-axis-y" }, item.label.length > 26 ? `${item.label.slice(0, 25)}…` : item.label),
        group,
        element("text", { x: left + scale(item.value) + 6, y: rowTop + 11, class: "att-axis att-axis-start" }, formatNumber(item.value)),
      );
    });
    finish(host, svg, options.legend);
  }

  function renderHeatmap(host, payload) {
    const cells = (payload.cells || []).filter((cell) => cell.mean != null);
    if (!cells.length) return showMessage(host, "No known attendance with a kickoff time to chart.");
    const weekdays = payload.weekdays || [];
    const HEAT_LEFT = 44;
    const HEAT_TOP = 22;
    const CELL_W = 34;
    const CELL_H = 30;
    const width = HEAT_LEFT + CELL_W * 24 + 8;
    const height = HEAT_TOP + CELL_H * weekdays.length + 8;
    const lookup = new Map((payload.cells || []).map((cell) => [`${cell.weekday}:${cell.hour}`, cell]));
    const means = cells.map((cell) => cell.mean);
    const low = Math.min(...means);
    const high = Math.max(...means);
    const svg = newSvg({ width, height }, "att-heat-svg");
    for (let hour = 0; hour < 24; hour += 1) {
      svg.append(element("text", { x: HEAT_LEFT + CELL_W * hour + CELL_W / 2, y: HEAT_TOP - 7, class: "att-axis att-axis-x" }, String(hour).padStart(2, "0")));
    }
    weekdays.forEach((label, row) => {
      svg.append(element("text", { x: HEAT_LEFT - 8, y: HEAT_TOP + CELL_H * row + CELL_H / 2 + 3, class: "att-axis att-axis-y" }, label));
      for (let hour = 0; hour < 24; hour += 1) {
        const cell = lookup.get(`${row}:${hour}`);
        const x = HEAT_LEFT + CELL_W * hour;
        const y = HEAT_TOP + CELL_H * row;
        const group = element("g", { class: "att-heat-cell" });
        if (!cell) {
          group.append(element("rect", { x, y, width: CELL_W - 2, height: CELL_H - 2, rx: 2, class: "att-heat-empty" }));
          svg.append(group);
          continue;
        }
        const known = cell.mean != null;
        const tip = known
          ? `${label} ${String(hour).padStart(2, "0")}:00 — mean ${formatNumber(cell.mean)}, ${cell.known} of ${cell.played} matches known`
          : `${label} ${String(hour).padStart(2, "0")}:00 — no known attendance (${cell.played} played)`;
        group.append(element("title", {}, tip));
        if (!known) {
          group.append(element("rect", { x, y, width: CELL_W - 2, height: CELL_H - 2, rx: 2, class: "att-heat-unknown" }));
        } else {
          const intensity = high === low ? 1 : (cell.mean - low) / (high - low);
          group.append(
            element("rect", { x, y, width: CELL_W - 2, height: CELL_H - 2, rx: 2, class: "att-heat-fill", "fill-opacity": (0.18 + 0.82 * intensity).toFixed(2) }),
            element("text", { x: x + (CELL_W - 2) / 2, y: y + 13, class: "att-heat-value" }, compactNumber(cell.mean)),
            element("text", { x: x + (CELL_W - 2) / 2, y: y + 24, class: "att-heat-count" }, `n=${cell.known}`),
          );
        }
        svg.append(group);
      }
    });
    finish(host, svg, `Cell: mean attendance and known matches (n). Darker is higher, from ${formatNumber(low)} to ${formatNumber(high)}. Cells based on few matches are noisy.`);
  }

  function bucketItems(rows) {
    return rows.map((row) => ({
      label: row.label,
      value: row.mean,
      tip: row.mean == null
        ? `${row.label}: no known attendance (${row.played} played)`
        : `${row.label}: mean ${formatNumber(row.mean)}, ${row.known} of ${row.played} matches known`,
    }));
  }

  const BUCKET_LEGEND = "Mean attendance of matches with known attendance.";

  function selectedCity(host, data) {
    const details = data.cityDetails || [];
    const panel = host.closest("[data-attendance-panel]");
    const select = panel && panel.querySelector("[data-city-select]");
    const index = select ? Number(select.value) : 0;
    return details[index] || details[0] || null;
  }

  function cityRowItems(rows) {
    return rows.map((row) => ({
      label: row.name,
      value: row.total,
      tip: `${row.name}: ${formatNumber(row.total)} spectators, mean ${row.mean == null ? "n/a" : formatNumber(row.mean)}, ${row.known} matches known`,
    }));
  }

  function renderCityTrend(host, data) {
    const city = selectedCity(host, data);
    if (!city) return showMessage(host, "No city with known attendance.");
    renderColumns(
      host,
      city.seasons.map((row) => ({
        label: row.season,
        value: row.total,
        tip: `${city.name} ${row.season}: ${formatNumber(row.total)} spectators, mean ${row.mean == null ? "n/a" : formatNumber(row.mean)}, median ${row.median == null ? "n/a" : formatNumber(row.median)}, ${row.known} of ${row.played} matches known`,
      })),
      { size: WIDE, labelWidth: 70, legend: `Total spectators per season in ${city.name}.`, empty: `No seasons with known attendance in ${city.name}.` },
    );
  }

  function renderCityCompetitions(host, data) {
    const city = selectedCity(host, data);
    if (!city) return showMessage(host, "No city with known attendance.");
    renderRows(host, cityRowItems(city.competitions), { legend: `Total spectators by competition in ${city.name}.`, empty: `No competitions with known attendance in ${city.name}.` });
  }

  function renderCityVenues(host, data) {
    const city = selectedCity(host, data);
    if (!city) return showMessage(host, "No city with known attendance.");
    renderRows(host, cityRowItems(city.venues), { legend: `Total spectators by venue in ${city.name}.`, empty: `No venues with known attendance in ${city.name}.` });
  }

  const RENDERERS = {
    trend: (host, data) => renderTrend(host, data.trend || {}),
    coverage: (host, data) => renderCoverage(host, data.coverage || []),
    clubs: (host, data) =>
      renderRows(
        host,
        (data.clubs || []).map((row) => ({ label: row.name, value: row.mean, tip: `${row.name}: mean ${row.mean == null ? "n/a" : formatNumber(row.mean)}, ${row.known} matches known` })),
        { legend: "Mean home attendance of the top clubs.", empty: "No clubs with known attendance." },
      ),
    cities: (host, data) =>
      renderRows(
        host,
        (data.cities || []).map((row) => ({
          label: row.name,
          value: row.total,
          tip: `${row.name}: ${formatNumber(row.total)} spectators, mean ${row.mean == null ? "n/a" : formatNumber(row.mean)}, ${row.known} matches known`,
        })),
        { legend: "Total spectators by match venue city, top 15.", empty: "No cities with known attendance." },
      ),
    cityTrend: renderCityTrend,
    cityCompetitions: renderCityCompetitions,
    cityVenues: renderCityVenues,
    heatmap: (host, data) => renderHeatmap(host, data.heatmap || {}),
    months: (host, data) => renderColumns(host, bucketItems(data.months || []), { legend: BUCKET_LEGEND }),
    weekdays: (host, data) => renderColumns(host, bucketItems(data.weekdays || []), { legend: BUCKET_LEGEND }),
    hours: (host, data) => renderColumns(host, bucketItems(data.hours || []), { legend: BUCKET_LEGEND, labelWidth: 52 }),
    opponents: (host, data) =>
      renderRows(
        host,
        (data.opponents || []).map((row) => ({
          label: row.name,
          value: row.mean,
          tip: `${row.name}: mean ${row.mean == null ? "n/a" : formatNumber(row.mean)}${row.difference == null ? "" : `, ${row.difference >= 0 ? "+" : "−"}${formatNumber(Math.abs(row.difference))} vs club mean`}`,
        })),
        { legend: "Mean attendance at the selected club's home matches by opponent.", empty: "No opponents with known attendance." },
      ),
    histogram: (host, data) =>
      renderColumns(
        host,
        (data.histogram || []).map((bin) => ({
          label: bin.label,
          value: bin.count,
          tip: `${bin.label}: ${formatNumber(bin.count)} matches (${(bin.share * 100).toFixed(1)}%)`,
        })),
        { size: WIDE, labelWidth: 84, legend: "Matches per attendance range.", empty: "No attendance distribution to chart." },
      ),
    weekdayEffect: (host, data) =>
      renderColumns(
        host,
        (data.weekdayEffect || []).map((row) => ({
          label: row.label,
          value: row.mean,
          tip: `${row.label}: mean ${row.mean == null ? "n/a" : formatNumber(row.mean)}, ${row.n} matches`,
        })),
        { legend: "Mean attendance by kickoff weekday in the analysed sample.", empty: "No matches with a kickoff time." },
      ),
  };

  class AttendanceCharts {
    constructor(root) {
      this.node = root.querySelector("#attendance-charts-data");
      this.data = null;
      if (!this.node) return;
      try {
        this.data = JSON.parse(this.node.textContent);
      } catch (_error) {
        this.data = null;
      }
    }

    draw(scope, selector) {
      scope.querySelectorAll(selector || "[data-chart]").forEach((host) => {
        const render = RENDERERS[host.dataset.chart];
        if (!render) return;
        if (!this.data) return showMessage(host, "Could not draw the chart.");
        try {
          render(host, this.data);
        } catch (_error) {
          showMessage(host, "Could not draw the chart.");
        }
      });
    }
  }

  class AttendanceTabs {
    constructor(root, charts) {
      this.root = root;
      this.charts = charts;
      this.bar = root.querySelector("[data-attendance-tabs]");
      this.drawn = new Set();
    }

    start() {
      if (!this.bar) return;
      this.buttons = Array.from(this.bar.querySelectorAll("[role=tab]"));
      this.panels = Array.from(this.root.querySelectorAll("[data-attendance-panel]"));
      this.panels.forEach((panel) => {
        panel.setAttribute("role", "tabpanel");
        panel.tabIndex = 0;
      });
      this.bar.hidden = false;
      this.buttons.forEach((button, index) => {
        button.addEventListener("click", () => this.select(index, true));
        button.addEventListener("keydown", (event) => {
          const next = {
            ArrowRight: (index + 1) % this.buttons.length,
            ArrowLeft: (index + this.buttons.length - 1) % this.buttons.length,
            Home: 0,
            End: this.buttons.length - 1,
          };
          if (!(event.key in next)) return;
          event.preventDefault();
          this.select(next[event.key], true);
          this.buttons[next[event.key]].focus();
        });
      });
      const wanted = new URLSearchParams(window.location.search).get("tab");
      const index = this.buttons.findIndex((button) => button.dataset.tab === wanted);
      this.select(index >= 0 ? index : 0, false);
    }

    select(index, persist) {
      this.buttons.forEach((button, number) => {
        button.setAttribute("aria-selected", String(number === index));
        button.tabIndex = number === index ? 0 : -1;
      });
      const id = this.buttons[index].getAttribute("aria-controls");
      this.panels.forEach((panel) => {
        panel.hidden = panel.id !== id;
        if (!panel.hidden) this.show(panel);
      });
      if (persist) this.remember(this.buttons[index].dataset.tab);
    }

    show(panel) {
      if (this.drawn.has(panel.id)) return;
      this.drawn.add(panel.id);
      this.charts.draw(panel);
    }

    remember(tab) {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", tab);
      window.history.replaceState(null, "", url);
    }
  }

  function filterTable(table, query) {
    const body = table.tBodies[0];
    const empty = body.querySelector(".att-empty");
    let visible = 0;
    body.querySelectorAll("tr[data-search-text]").forEach((row) => {
      const match = !query || row.dataset.searchText.includes(query);
      row.hidden = !match;
      if (match) visible += 1;
    });
    if (empty) empty.hidden = visible > 0;
  }

  function bindSearch(root) {
    root.querySelectorAll("[data-attendance-search]").forEach((input) => {
      const tables = [...root.querySelectorAll("[data-attendance-table]")].filter(
        (table) => table.dataset.attendanceTable === input.dataset.attendanceSearch,
      );
      input.addEventListener("input", () => {
        const query = input.value.trim().toLowerCase();
        tables.forEach((table) => filterTable(table, query));
      });
    });
  }

  const page = document.querySelector("[data-attendance]");
  if (!page) return;
  function bindCitySelect(root, charts) {
    root.querySelectorAll("[data-city-select]").forEach((select) => {
      select.addEventListener("change", () => {
        const panel = select.closest("[data-attendance-panel]");
        if (panel) charts.draw(panel, "[data-city-chart]");
      });
    });
  }

  bindSearch(page);
  const charts = new AttendanceCharts(page);
  bindCitySelect(page, charts);
  new AttendanceTabs(page, charts).start();
})();
