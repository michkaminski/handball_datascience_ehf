(() => {
  const root = document.querySelector('[data-maf]');
  if (!root) return;
  const panel = root.closest('[data-attendance-panel]') || root;
  const urls = root.dataset;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const COLORS = {primary: '#2b6ea4', secondary: '#3a7c67', accent: '#9f6a15', negative: '#b04646', neutral: '#64748b', grid: '#e5eaf0', dark: '#10283f'};
  const PALETTE = ['#2b6ea4', '#3a7c67', '#9f6a15', '#7a4f9a', '#b04646', '#1f8a9c'];
  const ROW_LIMIT = 50;
  const LOCALE = 'en-GB';
  const STATUS_LABELS = {ok: 'ok', ostrzezenie: 'warning', niewiarygodny: 'unreliable'};
  const SCALE_LABELS = {'wypełnienie hali': 'venue fill rate', 'log10(liczba widzów)': 'log10(spectators)'};
  const FILL_SCALE = 'wypełnienie hali';

  const state = {
    model: null,
    data: null,
    charts: new Map(),
    sorting: {field: 'iaf', direction: -1},
    limit: ROW_LIMIT,
    selected: new Set(),
    trends: [],
    started: false,
  };

  const element = selector => root.querySelector(selector);
  const html = text => String(text ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const number = (value, digits = 0) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
    return Number(value).toLocaleString(LOCALE, {minimumFractionDigits: digits, maximumFractionDigits: digits});
  };
  const percent = (value, digits = 1) => (value === null || value === undefined ? '—' : `${number(100 * value, digits)}%`);
  const signed = (value, digits = 1) => (value === null || value === undefined ? '—' : `${value > 0 ? '+' : ''}${number(value, digits)}`);
  const urlFor = (template, id) => template.replace(/\/0(?=\/?$|\?)/, `/${id}`);
  const withParams = (base, params) => `${base}?${new URLSearchParams(params).toString()}`;
  const isFill = () => state.data?.model?.measure === 'fill';
  const date = text => (text ? new Date(text).toLocaleDateString(LOCALE) : '—');
  const statusLabel = value => STATUS_LABELS[value] || value;

  const fetchJson = async url => {
    const response = await fetch(url, {headers: {Accept: 'application/json'}});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || `Error ${response.status}`);
    return body;
  };

  let echartsLoading = null;
  const echarts = () => {
    if (window.echarts) return Promise.resolve(window.echarts);
    if (!echartsLoading) {
      const url = root.dataset.echartsUrl || root.closest('[data-echarts-url]')?.dataset.echartsUrl;
      echartsLoading = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = () => resolve(window.echarts);
        script.onerror = reject;
        document.head.append(script);
      });
    }
    return echartsLoading;
  };

  const draw = async (name, options) => {
    const host = root.querySelector(`[data-maf-chart="${name}"]`);
    if (!host) return;
    const library = await echarts();
    let chart = state.charts.get(name);
    if (!chart) {
      chart = library.init(host, null, {renderer: 'svg'});
      state.charts.set(name, chart);
    }
    chart.setOption({animation: !reducedMotion, animationDuration: 300, ...options}, true);
  };
  window.addEventListener('resize', () => state.charts.forEach(chart => chart.resize()));

  const katex = (formula, display = true) => {
    if (window.katex) {
      try { return window.katex.renderToString(formula, {displayMode: display, throwOnError: false}); } catch (error) { return html(formula); }
    }
    return `<code>${html(formula)}</code>`;
  };

  const popover = root.parentElement.querySelector('[data-maf-popover]');
  const conceptLink = key => {
    const metric = state.data?.links?.metrics?.[key];
    if (!metric) return null;
    return {...state.data.links.concepts[metric.concept], url: metric.url};
  };
  const infoIcon = key => `<button type="button" class="maf-info" data-maf-info-button="${html(key)}" aria-label="Mathematical definition">i</button>`;
  const placeIcons = (scope = root) => {
    scope.querySelectorAll('span[data-maf-info]').forEach(slot => {
      if (conceptLink(slot.dataset.mafInfo)) slot.outerHTML = infoIcon(slot.dataset.mafInfo);
    });
  };
  const showPopover = (button, pin) => {
    const concept = conceptLink(button.dataset.mafInfoButton);
    if (!concept || !popover) return;
    const anchors = concept.anchors || {};
    popover.innerHTML = `<b>${html(concept.name)}</b><p>${html(concept.summary)}</p><nav>
      <a href="${html(anchors.definition || concept.url)}">Definition</a>
      <a href="${html(anchors.formula || concept.url)}">Formula</a>
      <a href="${html(anchors.derivation || concept.url)}">Derivation</a>
      <a href="${html(anchors.example || concept.url)}">Example</a>
      <a href="${html(state.data.links.model)}">Full model documentation</a></nav>`;
    popover.hidden = false;
    popover.dataset.pinned = pin ? '1' : '';
    const rect = button.getBoundingClientRect();
    const parent = popover.offsetParent?.getBoundingClientRect() || {left: 0, top: 0};
    popover.style.left = `${Math.max(8, rect.left - parent.left - 10)}px`;
    popover.style.top = `${rect.bottom - parent.top + 6}px`;
  };
  panel.addEventListener('mouseover', event => {
    const button = event.target.closest('[data-maf-info-button]');
    if (button && popover?.dataset.pinned !== '1') showPopover(button, false);
  });
  panel.addEventListener('mouseout', event => {
    if (event.target.closest('[data-maf-info-button]') && popover?.dataset.pinned !== '1') popover.hidden = true;
  });
  panel.addEventListener('click', event => {
    const button = event.target.closest('[data-maf-info-button]');
    if (button) {
      event.preventDefault();
      showPopover(button, true);
      return;
    }
    if (popover && !event.target.closest('[data-maf-popover]')) {
      popover.hidden = true;
      popover.dataset.pinned = '';
    }
  });

  const status = () => {
    const model = state.data.model;
    const diagnostics = state.data.diagnostics;
    const description = {
      ok: 'The model passed the convergence diagnostics (R-hat < 1.01, ESS ≥ 400, no divergences).',
      ostrzezenie: 'The diagnostics report warnings — treat the results with caution, especially for individual clubs.',
      niewiarygodny: 'The model did NOT pass the basic diagnostics. The results should not be interpreted as reliable.',
    }[model.status];
    element('[data-maf-status]').innerHTML = `<div class="maf-status ${html(model.status)}">
      <b>${html(model.label)}</b><span>${html(description)}</span>
      <span class="maf-meta">Version ${html(model.version)} · trained ${date(model.trained_at)} · ${number(model.matches_used)} matches · ${html(model.period.from || '')} – ${html(model.period.to || '')} · max R-hat ${number(diagnostics.max_rhat, 3)} ${infoIcon('rhat')} · min ESS ${number(diagnostics.min_ess_bulk)} ${infoIcon('ess')}</span></div>`;
  };

  const kpi = () => {
    const k = state.data.kpi;
    const bestEffect = k.best_effect;
    const items = [
      ['Total attendance', number(k.total), 'Sum of spectators in matches used by the model', 'suma'],
      ['Mean attendance', number(k.mean), `Arithmetic mean; standard deviation ${number(k.sd)}`, 'srednia'],
      ['Median attendance', number(k.median), 'Half of the matches had fewer spectators', 'mediana'],
      ['Mean venue fill rate', isFill() ? percent(k.fill_mean) : 'n/a', isFill() ? 'Mean of A/C, known capacity only' : 'Spectator-count model — no fictitious fill rate', 'wypelnienie'],
      ['Matches', number(k.matches), `Including ${number(k.reliable_clubs)} clubs with a reliable IAF`, 'mecze'],
      ['Highest attendance', number(k.top_match?.actual), k.top_match ? `${html(k.top_match.host)} – ${html(k.top_match.opponent)}, ${date(k.top_match.kickoff)}` : '', 'rekord'],
      ['Largest positive opponent effect', bestEffect ? `${signed(bestEffect.value, isFill() ? 1 : 0)} ${html(bestEffect.unit)}` : '—', bestEffect ? html(bestEffect.name) : 'no reliable estimates', 'efekt_pp'],
      ['Highest IAF index', k.best_iaf ? number(k.best_iaf.value, 1) : '—', k.best_iaf ? `${html(k.best_iaf.name)} (posterior median)` : 'no reliable estimates', 'iaf'],
    ];
    element('[data-maf-kpis]').innerHTML = items.map(([label, value, description, key]) => `<div class="maf-kpi">
      <div class="maf-kpi-label">${html(label)} ${infoIcon(key)}</div>
      <div class="maf-kpi-value">${value}</div><div class="maf-kpi-desc">${description}</div></div>`).join('');
  };

  const opponentClubs = () => (state.data?.clubs || []).filter(club => club.away);
  const fieldValue = (club, field) => {
    const a = club.away;
    return {
      name: club.name.toLowerCase(), matches: a.matches, mean: a.mean, median: a.median,
      fill: a.fill_mean ?? -1, iaf: a.iaf.median, effect: isFill() ? (a.pp?.median ?? 0) : a.extra.median,
      p: a.p_gt_100, width: a.iaf.q975 - a.iaf.q025,
    }[field];
  };

  const filtered = () => {
    const phrase = element('[data-maf-search]').value.trim().toLowerCase();
    const reliableOnly = element('[data-maf-reliable]').checked;
    const minimum = Number(element('[data-maf-min]').value);
    const {field, direction} = state.sorting;
    return opponentClubs()
      .filter(club => !phrase || club.name.toLowerCase().includes(phrase) || (club.names_history || []).some(name => name.toLowerCase().includes(phrase)))
      .filter(club => !reliableOnly || club.away.reliable)
      .filter(club => club.away.matches >= minimum)
      .sort((a, b) => {
        const x = fieldValue(a, field);
        const y = fieldValue(b, field);
        return (x < y ? -1 : x > y ? 1 : 0) * direction;
      });
  };

  const intervalBar = iaf => {
    const min = 50;
    const max = 170;
    const position = value => `${Math.max(0, Math.min(100, (value - min) / (max - min) * 100))}%`;
    return `<span class="maf-ci" title="95%: ${number(iaf.q025, 1)} – ${number(iaf.q975, 1)}"><em style="left:${position(100)}"></em><span style="left:${position(iaf.q025)};width:calc(${position(iaf.q975)} - ${position(iaf.q025)})"></span><i style="left:${position(iaf.median)}"></i></span>`;
  };

  const ranking = () => {
    const table = element('[data-maf-ranking]');
    const rows = filtered();
    const headers = [
      ['#', null], ['', null], ['Club', 'name'], ['Matches (away)', 'matches'], ['Mean', 'mean'], ['Median', 'median'],
      ['Fill rate', 'fill'], ['IAF', 'iaf'], [isFill() ? 'Effect p.p.' : 'Extra spectators', 'effect'],
      ['P(IAF > 100)', 'p'], ['95% interval', 'width'], ['', null],
    ];
    const headerIcons = {IAF: 'iaf', 'Effect p.p.': 'efekt_pp', 'Extra spectators': 'efekt_rywala', 'P(IAF > 100)': 'p_iaf', '95% interval': 'przedzial', Mean: 'srednia', Median: 'mediana'};
    const head = headers.map(([text, field]) => {
      const sort = field ? ` data-sort="${field}" aria-sort="${state.sorting.field === field ? (state.sorting.direction > 0 ? 'ascending' : 'descending') : 'none'}"` : '';
      const icon = headerIcons[text] ? ` ${infoIcon(headerIcons[text])}` : '';
      return `<th scope="col" class="${field && field !== 'name' ? 'num' : ''}"${sort}>${html(text)}${icon}</th>`;
    }).join('');
    const body = rows.slice(0, state.limit).map((club, index) => {
      const a = club.away;
      const effect = isFill() ? `${signed(a.pp?.median, 1)}` : signed(a.extra.median, 0);
      const assessment = a.reliable ? '' : ` <span class="maf-badge warn" title="${html(a.notes.join('; '))}">uncertain</span>`;
      return `<tr class="maf-row" data-club="${club.id}">
        <td class="num">${index + 1}</td>
        <td><input type="checkbox" aria-label="Select for comparison" data-maf-select="${club.id}"${state.selected.has(club.id) ? ' checked' : ''}></td>
        <td><a href="${urlFor(urls.urlTeam, club.id)}">${html(club.name)}</a>${assessment}</td>
        <td class="num">${number(a.matches)}</td><td class="num">${number(a.mean)}</td><td class="num">${number(a.median)}</td>
        <td class="num">${a.fill_mean === null || a.fill_mean === undefined ? 'n/a' : percent(a.fill_mean)}</td>
        <td class="num"><b>${number(a.iaf.median, 1)}</b></td>
        <td class="num ${(isFill() ? a.pp?.median : a.extra.median) > 0 ? 'maf-up' : 'maf-down'}">${effect}</td>
        <td class="num">${percent(a.p_gt_100, 1)}</td>
        <td class="num">${intervalBar(a.iaf)}${number(a.iaf.q025, 1)} – ${number(a.iaf.q975, 1)}</td>
        <td><button type="button" class="btn secondary small" data-maf-trace="${club.id}">How computed?</button></td></tr>`;
    }).join('');
    table.innerHTML = `<caption class="sr-only">Ranking of clubs by IAF</caption><thead><tr>${head}</tr></thead><tbody>${body || '<tr><td colspan="12" class="note">No clubs for these filters.</td></tr>'}</tbody>`;
    element('[data-maf-more]').hidden = rows.length <= state.limit;
    element('[data-maf-export]').href = withParams(urls.urlExport, {model: state.model});
  };

  const rowDetails = row => {
    const next = row.nextElementSibling;
    if (next?.classList.contains('maf-detail')) { next.remove(); return; }
    const club = state.data.clubs.find(item => item.id === Number(row.dataset.club));
    const a = club.away;
    const home = club.home;
    const seasons = (a.by_season || []).map(season => `<tr><td>${html(season.season)}</td><td class="num">${number(season.matches)}</td><td class="num">${number(season.median, 1)}</td><td class="num">${number(season.q025, 1)} – ${number(season.q975, 1)}</td></tr>`).join('');
    const detail = document.createElement('tr');
    detail.className = 'maf-detail';
    detail.innerHTML = `<td colspan="12"><div class="maf-two">
      <div><h5>As opponent (away)</h5><dl class="maf-kv">
        <dt>Matches / distinct hosts</dt><dd>${number(a.matches)} / ${number(a.hosts)}</dd>
        <dt>Seasons</dt><dd>${html((a.seasons || []).join(', '))}</dd>
        <dt>Effect R<sub>j</sub> (${isFill() ? 'logit' : 'log'} scale)</dt><dd>${number(a.effect.median, 3)} [${number(a.effect.q025, 3)}; ${number(a.effect.q975, 3)}]</dd>
        <dt>Extra spectators (reference venue)</dt><dd>${signed(a.extra.median, 0)} [${signed(a.extra.q025, 0)}; ${signed(a.extra.q975, 0)}]</dd>
        <dt>R-hat / ESS</dt><dd>${number(a.rhat, 3)} / ${number(a.ess_bulk)}</dd>
        <dt>Notes</dt><dd>${a.notes.length ? html(a.notes.join('; ')) : 'reliable estimate'}</dd>
        ${club.names_history?.length > 1 ? `<dt>Historical names</dt><dd>${html(club.names_history.join(' · '))}</dd>` : ''}
      </dl></div>
      <div><h5>As host (own crowd)</h5>${home ? `<dl class="maf-kv">
        <dt>Home matches</dt><dd>${number(home.matches)}</dd><dt>Mean / median</dt><dd>${number(home.mean)} / ${number(home.median)}</dd>
        ${home.fill_mean !== null && home.fill_mean !== undefined ? `<dt>Mean fill rate</dt><dd>${percent(home.fill_mean)}</dd>` : ''}
        <dt>Host strength index</dt><dd>${number(home.index.median, 1)} [${number(home.index.q025, 1)}; ${number(home.index.q975, 1)}]</dd>
      </dl>` : '<p class="note">No home matches in the model.</p>'}
      ${seasons ? `<h5>IAF by season</h5><table class="att-table"><thead><tr><th>Season</th><th class="num">Matches</th><th class="num">IAF</th><th class="num">95%</th></tr></thead><tbody>${seasons}</tbody></table>` : ''}</div></div></td>`;
    row.after(detail);
  };

  const compare = async () => {
    const [a, b] = [...state.selected];
    const slot = element('[data-maf-compare-result]');
    try {
      const result = await fetchJson(withParams(urls.urlCompare, {model: state.model, a, b}));
      const name = id => state.data.clubs.find(club => club.id === id)?.name || id;
      slot.innerHTML = `<div class="maf-note-box">P(IAF<sub>${html(name(a))}</sub> &gt; IAF<sub>${html(name(b))}</sub> | data) = <b>${percent(result.p_first_greater, 1)}</b> (± ${percent(result.mcse, 1)} Monte Carlo error) ${infoIcon('p_iaf')}.
        Difference of medians ${signed(result.difference.median, 1)} pts, 95% interval of the difference ${number(result.difference.q025, 1)} – ${number(result.difference.q975, 1)}.</div>`;
    } catch (error) {
      slot.innerHTML = `<p class="att-warning">${html(error.message)}</p>`;
    }
  };

  const refreshCompareButton = () => {
    const button = element('[data-maf-compare]');
    button.disabled = state.selected.size !== 2;
    button.textContent = `Compare selected (${state.selected.size}/2)`;
  };

  const forest = () => {
    const sort = element('[data-maf-forest-sort]').value;
    const limit = Number(element('[data-maf-forest-limit]').value);
    const reliableOnly = element('[data-maf-forest-reliable]').checked;
    const order = {
      iaf: (a, b) => b.away.iaf.median - a.away.iaf.median,
      narrow: (a, b) => (a.away.iaf.q975 - a.away.iaf.q025) - (b.away.iaf.q975 - b.away.iaf.q025),
      wide: (a, b) => (b.away.iaf.q975 - b.away.iaf.q025) - (a.away.iaf.q975 - a.away.iaf.q025),
      matches: (a, b) => b.away.matches - a.away.matches,
    }[sort];
    const reliable = opponentClubs().filter(club => club.away.reliable);
    const source = reliableOnly && reliable.length ? reliable : opponentClubs();
    element('[data-maf-forest-note]').textContent = reliableOnly && !reliable.length
      ? 'No estimate meets the reliability criteria — all clubs are shown.'
      : '';
    const clubs = source.sort(order).slice(0, limit).reverse();
    const names = clubs.map(club => club.name);
    draw('forest', {
      grid: {left: 210, right: 30, top: 20, bottom: 40},
      tooltip: {trigger: 'item', formatter: p => {
        const club = clubs[p.dataIndex];
        if (!club) return '';
        const a = club.away;
        return `<b>${html(club.name)}</b><br>IAF (median): ${number(a.iaf.median, 1)}<br>95%: ${number(a.iaf.q025, 1)} – ${number(a.iaf.q975, 1)}<br>P(IAF > 100): ${percent(a.p_gt_100)}<br>Matches: ${a.matches}`;
      }},
      xAxis: {type: 'value', name: 'IAF', nameLocation: 'middle', nameGap: 26, scale: true, splitLine: {lineStyle: {color: COLORS.grid}}},
      yAxis: {type: 'category', data: names, axisLabel: {fontSize: 11, width: 200, overflow: 'truncate'}},
      series: [
        {type: 'custom', name: '95% interval', renderItem: (params, api) => {
          const y = api.coord([0, api.value(0)])[1];
          const from = api.coord([api.value(1), api.value(0)])[0];
          const to = api.coord([api.value(2), api.value(0)])[0];
          return {type: 'group', children: [
            {type: 'line', shape: {x1: from, y1: y, x2: to, y2: y}, style: {stroke: COLORS.primary, lineWidth: 2}},
            {type: 'line', shape: {x1: from, y1: y - 4, x2: from, y2: y + 4}, style: {stroke: COLORS.primary, lineWidth: 1.5}},
            {type: 'line', shape: {x1: to, y1: y - 4, x2: to, y2: y + 4}, style: {stroke: COLORS.primary, lineWidth: 1.5}},
          ]};
        }, encode: {x: [1, 2], y: 0}, data: clubs.map((club, i) => [i, club.away.iaf.q025, club.away.iaf.q975]), z: 1},
        {type: 'scatter', name: 'median', symbolSize: 9, itemStyle: {color: COLORS.dark}, data: clubs.map((club, i) => [club.away.iaf.median, i]), encode: {x: 0, y: 1},
          markLine: {silent: true, symbol: 'none', lineStyle: {color: COLORS.negative, type: 'dashed'}, label: {formatter: 'IAF = 100'}, data: [{xAxis: 100}]}},
      ],
    });
  };

  const clubOptions = (list, chosen) => list.map(club => `<option value="${club.id}"${club.id === chosen ? ' selected' : ''}>${html(club.name)}</option>`).join('');

  const trends = () => {
    const clubs = state.trends.map(id => state.data.clubs.find(club => club.id === id)).filter(Boolean);
    element('[data-maf-trend-chips]').innerHTML = `<span class="maf-chips">${clubs.map(club => `<span class="maf-chip">${html(club.name)} <button type="button" data-maf-trend-remove="${club.id}" aria-label="Remove">×</button></span>`).join('')}</span>`;
    const seasons = state.data.model.seasons;
    const series = [];
    clubs.forEach((club, index) => {
      const color = PALETTE[index % PALETTE.length];
      const map = new Map((club.away.by_season || []).map(season => [season.season, season]));
      const lower = seasons.map(s => map.get(s)?.q10 ?? null);
      const upper = seasons.map(s => (map.has(s) ? map.get(s).q90 - map.get(s).q10 : null));
      series.push({type: 'line', stack: `band${index}`, data: lower, lineStyle: {opacity: 0}, symbol: 'none', silent: true, tooltip: {show: false}});
      series.push({type: 'line', stack: `band${index}`, data: upper, lineStyle: {opacity: 0}, symbol: 'none', areaStyle: {color, opacity: 0.14}, silent: true, tooltip: {show: false}});
      series.push({type: 'line', name: club.name, data: seasons.map(s => map.get(s)?.median ?? null), connectNulls: false, itemStyle: {color}, lineStyle: {width: 2, color}, symbol: ['circle', 'rect', 'triangle', 'diamond'][index % 4], symbolSize: 7});
    });
    draw('trend', {
      grid: {left: 50, right: 20, top: 30, bottom: 50},
      legend: {top: 0, data: clubs.map(club => club.name)},
      tooltip: {trigger: 'axis', valueFormatter: v => number(v, 1)},
      xAxis: {type: 'category', data: seasons, axisLabel: {rotate: seasons.length > 10 ? 35 : 0}},
      yAxis: {type: 'value', name: 'IAF', scale: true, splitLine: {lineStyle: {color: COLORS.grid}}},
      series: series.length ? [...series, {type: 'line', data: [], markLine: {silent: true, symbol: 'none', lineStyle: {color: COLORS.negative, type: 'dashed'}, data: [{yAxis: 100}]}}] : [],
    });
    element('[data-maf-trend-table]').innerHTML = clubs.length ? `<thead><tr><th>Club</th>${seasons.map(s => `<th class="num">${html(s)}</th>`).join('')}</tr></thead><tbody>${clubs.map(club => {
      const map = new Map((club.away.by_season || []).map(season => [season.season, season]));
      return `<tr><th scope="row">${html(club.name)}</th>${seasons.map(s => `<td class="num">${map.has(s) ? `${number(map.get(s).median, 1)}<br><small>${number(map.get(s).q025, 0)}–${number(map.get(s).q975, 0)}</small>` : '—'}</td>`).join('')}</tr>`;
    }).join('')}</tbody>` : '';
  };

  const posterior = async () => {
    const id = Number(element('[data-maf-posterior-select]').value);
    if (!id) return;
    try {
      const result = await fetchJson(withParams(urlFor(urls.urlClub, id), {model: state.model}));
      const a = result.club.away;
      const edges = a.histogram.edges;
      const centres = a.histogram.counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
      const total = a.histogram.counts.reduce((x, y) => x + y, 0) || 1;
      element('[data-maf-posterior-summary]').innerHTML = `median ${number(a.iaf.median, 1)}, 95% ${number(a.iaf.q025, 1)} – ${number(a.iaf.q975, 1)}, <b>P(IAF &gt; 100) = ${percent(a.p_gt_100, 1)}</b>`;
      draw('posterior', {
        grid: {left: 50, right: 20, top: 20, bottom: 40},
        tooltip: {trigger: 'axis', formatter: p => `IAF ≈ ${number(centres[p[0].dataIndex], 1)}<br>share of samples: ${percent(a.histogram.counts[p[0].dataIndex] / total, 1)}`},
        xAxis: {type: 'category', data: centres.map(v => number(v, 1)), name: 'IAF', nameLocation: 'middle', nameGap: 26},
        yAxis: {type: 'value', name: 'density (share of samples)', splitLine: {lineStyle: {color: COLORS.grid}}},
        series: [{type: 'bar', barCategoryGap: '4%', data: a.histogram.counts.map((count, i) => ({value: count / total, itemStyle: {color: centres[i] > 100 ? COLORS.secondary : '#b7c6d4'}}))}],
      });
    } catch (error) {
      element('[data-maf-posterior-summary]').textContent = error.message;
    }
  };

  const hostAnalysis = async () => {
    const id = Number(element('[data-maf-host-select]').value);
    const slot = element('[data-maf-host]');
    if (!id) return;
    slot.innerHTML = '<p class="note">Computing…</p>';
    try {
      const result = await fetchJson(withParams(urlFor(urls.urlHost, id), {model: state.model}));
      const table = (rows, title) => `<div><h4>${title}</h4><table class="att-table"><thead><tr><th>Opponent</th><th class="num">Visits</th><th class="num">Index at host</th><th class="num">95%</th><th class="num">P(&gt; 100)</th><th class="num">Δ spectators</th></tr></thead><tbody>${rows.map(r => `<tr><td>${html(r.name)}</td><td class="num">${r.visits}</td><td class="num"><b>${number(r.index.median, 1)}</b></td><td class="num">${number(r.index.q025, 1)} – ${number(r.index.q975, 1)}</td><td class="num">${percent(r.p_gt_100)}</td><td class="num">${signed(r.extra.median, 0)}</td></tr>`).join('') || '<tr><td colspan="6" class="note">No data</td></tr>'}</tbody></table></div>`;
      slot.innerHTML = `<p class="note">Expected attendance at ${html(result.host)} with a typical opponent: <b>${number(result.reference_expected.median)}</b> spectators (95%: ${number(result.reference_expected.q025)} – ${number(result.reference_expected.q975)})${result.capacity ? `, venue ~${number(result.capacity)} seats` : ''}. Own home mean (data): ${number(result.home_mean)}. The analysis covers ${result.opponents_total} opponents that played at this host.</p>
        ${result.uniform_ratio ? '<p class="maf-note-box">In the spectator-count model (log link) the opponent effect is multiplicative and the same relative to every host — only the number of spectators (Δ) differs.</p>' : '<p class="note">In the fill-rate model (logit link) the same opponent raises the fill rate differently at different hosts — the effect weakens when the venue is close to full.</p>'}
        <div class="maf-two">${table(result.top, 'Increase interest the most')}${table(result.bottom, 'Attract the least')}</div>`;
    } catch (error) {
      slot.innerHTML = `<p class="att-warning">${html(error.message)}</p>`;
    }
  };

  const prepareSimulator = () => {
    const clubs = [...state.data.clubs].sort((a, b) => a.name.localeCompare(b.name, 'en'));
    const hosts = clubs.filter(club => club.home);
    const opponents = clubs.filter(club => club.away);
    element('[data-maf-sim-host]').innerHTML = clubOptions(hosts);
    element('[data-maf-sim-opponent]').innerHTML = clubOptions(opponents);
    const opponentSelect = element('[data-maf-sim-opponent]');
    if (opponentSelect.value === element('[data-maf-sim-host]').value && opponentSelect.options.length > 1) {
      opponentSelect.selectedIndex = opponentSelect.selectedIndex === 0 ? 1 : 0;
    }
    element('[data-maf-sim-competition]').innerHTML = `<option value="">new / unknown</option>${state.data.competitions.map(c => `<option value="${html(c.key)}">${html(c.name)} (${c.matches})</option>`).join('')}`;
    const seasons = state.data.model.seasons;
    element('[data-maf-sim-season]').innerHTML = `<option value="">next season (new)</option>${[...seasons].reverse().map((s, i) => `<option value="${html(s)}"${i === 0 ? ' selected' : ''}>${html(s)}</option>`).join('')}`;
    element('[data-maf-sim-venue]').innerHTML = `<option value="">— enter capacity —</option>${state.data.venues.filter(v => v.capacity).map(v => `<option value="${v.id}" data-capacity="${v.capacity}" data-host="${v.main_host}">${html(v.name)} (${number(v.capacity)})</option>`).join('')}`;
    const setVenue = () => {
      const id = Number(element('[data-maf-sim-host]').value);
      const venue = [...element('[data-maf-sim-venue]').options].find(option => Number(option.dataset.host) === id);
      if (venue) {
        element('[data-maf-sim-venue]').value = venue.value;
        element('[data-maf-sim-capacity]').value = venue.dataset.capacity;
      } else {
        const host = state.data.hosts.find(h => h.id === id);
        element('[data-maf-sim-capacity]').value = host?.capacity ? Math.round(host.capacity) : '';
      }
      const competition = state.data.competitions[0];
      if (competition && !element('[data-maf-sim-competition]').value) element('[data-maf-sim-competition]').value = competition.key;
    };
    element('[data-maf-sim-host]').onchange = setVenue;
    element('[data-maf-sim-venue]').onchange = () => {
      const option = element('[data-maf-sim-venue]').selectedOptions[0];
      if (option?.dataset.capacity) element('[data-maf-sim-capacity]').value = option.dataset.capacity;
    };
    setVenue();
    element('[data-maf-sim-capacity]').required = isFill();
  };

  const simulate = async form => {
    const params = Object.fromEntries(new FormData(form).entries());
    params.model = state.model;
    Object.keys(params).forEach(key => { if (params[key] === '') delete params[key]; });
    const slot = element('[data-maf-sim-result]');
    slot.innerHTML = '<p class="note">Monte Carlo simulation…</p>';
    try {
      const r = await fetchJson(withParams(urls.urlForecast, params));
      const intervals = Object.entries(r.intervals).map(([level, [from, to]]) => `<tr><td>${level}%</td><td class="num">${number(from)} – ${number(to)}</td>${r.capacity ? `<td class="num">${percent(Math.min(from / r.capacity, 1), 0)} – ${percent(Math.min(to / r.capacity, 1), 0)}</td>` : ''}</tr>`).join('');
      const thresholds = r.fill_probabilities ? Object.entries(r.fill_probabilities).map(([level, p]) => `<tr><td>fill rate ≥ ${level}%</td><td class="num"><b>${percent(p, 1)}</b></td></tr>`).join('') : '';
      slot.innerHTML = `<div class="maf-sim-grid"><div>
        <dl class="maf-kv">
          <dt>Expected spectators ${infoIcon('wartosc_oczekiwana_prognozy')}</dt><dd>${number(r.expected)}</dd>
          <dt>Forecast median</dt><dd>${number(r.median)}</dd>
          ${r.fill_expected !== undefined ? `<dt>Forecast fill rate</dt><dd>${percent(r.fill_expected, 1)} (venue ${number(r.capacity)} seats)</dd>` : ''}
          <dt>Credible interval of the <i>mean</i> (parameter uncertainty only) ${infoIcon('przedzial')}</dt><dd>${number(r.mean_parameter.q025)} – ${number(r.mean_parameter.q975)}</dd>
          ${r.p_threshold !== undefined ? `<dt>P(spectators ≥ ${number(r.threshold)})</dt><dd>${percent(r.p_threshold, 1)}</dd>` : ''}
        </dl>
        <h4>Predictive intervals ${infoIcon('przedzial_predykcyjny')}</h4>
        <table class="att-table"><thead><tr><th>Level</th><th class="num">Spectators</th>${r.capacity ? '<th class="num">Fill rate</th>' : ''}</tr></thead><tbody>${intervals}</tbody></table>
        ${thresholds ? `<h4>Probability of filling the venue</h4><table class="att-table"><tbody>${thresholds}</tbody></table>` : ''}
        <p class="note">${r.draws} posterior samples × ${r.samples / r.draws} match draws = ${number(r.samples)} simulations. ${r.notes.map(html).join(' · ')}</p>
      </div><div class="att-chart" data-maf-chart="simulation" role="img" aria-label="Predictive distribution of the number of spectators; intervals and venue capacity marked."></div></div>`;
      const edges = r.histogram.edges;
      const centres = r.histogram.probabilities.map((_, i) => (edges[i] + edges[i + 1]) / 2);
      const [from95, to95] = r.intervals['95'];
      state.charts.get('simulation')?.dispose();
      state.charts.delete('simulation');
      draw('simulation', {
        grid: {left: 54, right: 20, top: 24, bottom: 44},
        tooltip: {trigger: 'axis', formatter: p => `${number(edges[p[0].dataIndex])} – ${number(edges[p[0].dataIndex + 1])} spectators<br>probability: ${percent(r.histogram.probabilities[p[0].dataIndex], 1)}`},
        xAxis: {type: 'category', data: centres.map(v => number(v)), name: 'Spectators', nameLocation: 'middle', nameGap: 28},
        yAxis: {type: 'value', name: 'P', axisLabel: {formatter: v => percent(v, 0)}, splitLine: {lineStyle: {color: COLORS.grid}}},
        series: [{type: 'bar', barCategoryGap: '3%', data: r.histogram.probabilities.map((p, i) => ({value: p, itemStyle: {color: centres[i] >= from95 && centres[i] <= to95 ? COLORS.primary : '#c3d0dc'}}))}],
      });
      placeIcons(slot);
    } catch (error) {
      slot.innerHTML = `<p class="att-warning">${html(error.message)}</p>`;
    }
  };

  const matchTable = (rows, records = false) => `<thead><tr><th>Date</th>${records ? '<th>Season</th>' : ''}<th>Match</th><th class="num">Spectators</th><th class="num">Expected</th><th class="num">Difference</th><th class="num">%</th>${isFill() ? '<th class="num">p.p.</th>' : ''}<th class="num">z</th><th class="num">p</th></tr></thead><tbody>${rows.map(m => `<tr>
    <td><a href="${urlFor(urls.urlMatch, m.match_id)}">${date(m.kickoff)}</a></td>${records ? `<td>${html(m.season)}</td>` : ''}
    <td>${html(m.host)} – ${html(m.opponent)}<br><small class="note">${html(m.competition)}</small></td>
    <td class="num"><b>${number(m.actual)}</b></td><td class="num">${number(m.expected)}<br><small class="note">90%: ${number(m.interval90[0])}–${number(m.interval90[1])}</small></td>
    <td class="num ${m.difference > 0 ? 'maf-up' : 'maf-down'}">${signed(m.difference, 0)}</td><td class="num">${signed(m.difference_pct, 0)}</td>
    ${isFill() ? `<td class="num">${signed(m.difference_pp, 1)}</td>` : ''}<td class="num">${number(m.z, 2)}</td><td class="num">${m.p_value < 0.001 ? '&lt;0.001' : number(m.p_value, 3)}</td></tr>`).join('')}</tbody>`;

  const deviations = () => {
    const surprises = state.data.surprises;
    element('[data-maf-surprises="positive"]').innerHTML = matchTable(surprises.positive.slice(0, 20));
    element('[data-maf-surprises="negative"]').innerHTML = matchTable(surprises.negative.slice(0, 20));
    const records = state.data.records;
    element('[data-maf-records="season"]').innerHTML = matchTable(records.season, true);
    element('[data-maf-records="club"]').innerHTML = matchTable(records.club.slice(0, 20), true);
    element('[data-maf-records="venue"]').innerHTML = matchTable(records.venue.slice(0, 20), true);
    const map = state.data.heatmap;
    draw('heatmap', {
      grid: {left: 200, right: 30, top: 10, bottom: 110},
      tooltip: {formatter: p => `${html(map.hosts[p.value[1]])}, ${html(map.seasons[p.value[0]])}<br>mean z = ${number(p.value[2], 2)} (${p.value[3]} matches)`},
      xAxis: {type: 'category', data: map.seasons, axisLabel: {rotate: 35}},
      yAxis: {type: 'category', data: map.hosts, axisLabel: {fontSize: 11, width: 190, overflow: 'truncate'}},
      visualMap: {dimension: 2, min: -2, max: 2, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, inRange: {color: ['#b04646', '#f4f6f8', '#2b6ea4']}, text: ['above expectations', 'below']},
      series: [{type: 'heatmap', data: map.values, label: {show: false}}],
    });
  };

  const diagnostics = () => {
    const d = state.data.diagnostics;
    const b = state.data.backtest;
    const m = state.data.model;
    const coefficients = state.data.coefficients.map(c => `<tr><td>${html(c.label)}</td><td class="num">${number(c.coefficient.median, 3)}</td><td class="num">${number(c.coefficient.q025, 3)} – ${number(c.coefficient.q975, 3)}</td><td class="num">${percent(c.p_positive, 0)}</td><td class="num">${signed(c.effect.median, 2)} ${html(c.effect_unit)}</td><td class="num">${number(c.rhat, 3)}</td><td class="num">${number(c.ess_bulk)}</td></tr>`).join('');
    const groups = m.groups.map(g => `<tr><td>${html(g.label)}</td><td class="num">${number(g.levels)}</td><td>${{fixed: 'fixed effect, N(0, 1)', centered: 'random, centred parameterisation', noncentered: 'random, non-centred'}[g.mode]}</td><td class="num">${g.sigma ? `${number(g.sigma.median, 3)} [${number(g.sigma.q025, 3)}; ${number(g.sigma.q975, 3)}]` : '—'}</td></tr>`).join('');
    const parameterName = name => {
      const match = /^beta\[(\d+)\]$/.exec(name);
      return match ? `β: ${m.features.labels[Number(match[1])] || name}` : name;
    };
    const keyParameters = d.key_parameters.map(p => `<tr><td><code>${html(parameterName(p.name))}</code></td><td class="num">${number(p.mean, 3)}</td><td class="num">${number(p.sd, 3)}</td><td class="num">${number(p.rhat, 3)}</td><td class="num">${number(p.ess_bulk)}</td><td class="num">${number(p.ess_tail)}</td></tr>`).join('');
    const coverage = b.available ? Object.values(b.coverage).map(c => `<tr><td>${percent(c.nominal, 0)}</td><td class="num"><b>${percent(c.observed, 1)}</b></td><td class="num">${number(c.mean_width)}</td></tr>`).join('') : '';
    const ppcRows = state.data.ppc.checks.map(c => `<tr><td>${html(c.statistic)}</td><td class="num">${number(c.observed, 3)}</td><td class="num">${number(c.replicated_q05, 3)} – ${number(c.replicated_q95, 3)}</td><td class="num">${number(c.p_value, 2)}</td></tr>`).join('');
    element('[data-maf-diagnostics]').innerHTML = `<div class="maf-two"><div>
      <h4>MCMC convergence (NUTS) ${infoIcon('mcmc')}</h4><dl class="maf-kv">
        <dt>Status</dt><dd>${html(statusLabel(d.status))}</dd><dt>Chains × draws</dt><dd>${d.chains} × ${d.draws_per_chain} (warm-up ${m.sampler.warmup})</dd>
        <dt>Max R-hat ${infoIcon('rhat')}</dt><dd>${number(d.max_rhat, 4)} (threshold ${number(d.thresholds.rhat, 2)}; ${percent(d.share_rhat_ok, 1)} of parameters &lt; 1.01)</dd>
        <dt>Min ESS bulk / tail ${infoIcon('ess')}</dt><dd>${number(d.min_ess_bulk)} / ${number(d.min_ess_tail)} (threshold ${number(d.thresholds.ess)})</dd>
        <dt>Divergences</dt><dd>${d.divergences}</dd><dt>E-BFMI</dt><dd>${d.ebfmi.map(v => number(v, 2)).join(' · ')}</dd>
        <dt>Step size</dt><dd>${d.step_sizes.map(v => number(v, 3)).join(' · ')}</dd><dt>Random seed</dt><dd>${m.sampler.seed}</dd>
        <dt>Data fingerprint (SHA-256)</dt><dd><code>${html(m.data_fingerprint.slice(0, 16))}…</code></dd>
      </dl></div><div>
      <h4>Chronological validation ${infoIcon('backtest')}</h4>${b.available ? `<dl class="maf-kv">
        <dt>Training → test</dt><dd>${html(b.train_seasons[0])}–${html(b.train_seasons[b.train_seasons.length - 1])} → ${html(b.test_seasons.join(', '))}</dd>
        <dt>Training / test matches</dt><dd>${number(b.train_matches)} / ${number(b.test_matches)}</dd>
        <dt>MAE ${infoIcon('mae')}</dt><dd>${number(b.mae)} spectators (baseline: ${number(b.baseline_mae)})</dd>
        <dt>RMSE ${infoIcon('rmse')}</dt><dd>${number(b.rmse)} (baseline: ${number(b.baseline_rmse)})</dd>
        ${b.mae_fill_pp !== undefined ? `<dt>Fill-rate MAE</dt><dd>${number(b.mae_fill_pp, 1)} p.p.</dd>` : ''}
        <dt>CRPS</dt><dd>${number(b.crps, 1)}</dd><dt>Training model diagnostics</dt><dd>${html(statusLabel(b.diagnostics_status))}</dd>
      </dl><p class="note">Baseline: ${html(b.baseline_label)}.</p>
      <h5>Predictive interval coverage ${infoIcon('pokrycie')}</h5><table class="att-table"><thead><tr><th>Nominal</th><th class="num">Observed</th><th class="num">Mean width</th></tr></thead><tbody>${coverage}</tbody></table>` : `<p class="note">${html(b.reason || 'none')}</p>`}</div></div>
      <h4>Match condition coefficients ${infoIcon('wspolczynniki')}</h4>
      <p class="note">Continuous covariates are standardised ${infoIcon('standaryzacja')} (coefficient = change per 1 standard deviation). The effect is shown on the outcome scale for the reference population. Form = mean points from the 5 previous matches ${infoIcon('forma')}. Correlation does not imply causation.</p>
      <div class="table-wrap att-table-wrap"><table class="att-table"><thead><tr><th>Factor</th><th class="num">β (median)</th><th class="num">95%</th><th class="num">P(β &gt; 0)</th><th class="num">Effect</th><th class="num">R-hat</th><th class="num">ESS</th></tr></thead><tbody>${coefficients}</tbody></table></div>
      <div class="maf-two"><div><h4>Hierarchical structure ${infoIcon('hierarchia')}</h4><table class="att-table"><thead><tr><th>Effect</th><th class="num">Levels</th><th>Type ${infoIcon('efekty_losowe')}</th><th class="num">σ ${infoIcon('hiperprior')}</th></tr></thead><tbody>${groups}</tbody></table>
      <p class="note">Effects have a sum-to-zero constraint ${infoIcon('identyfikowalnosc')} (globally for H, R, S, L; within a club for HS and RS), which is why IAF = 100 is the average opponent in the population.</p></div>
      <div><h4>Global parameters</h4><table class="att-table"><thead><tr><th>Parameter</th><th class="num">Mean</th><th class="num">SD</th><th class="num">R-hat</th><th class="num">ESS bulk</th><th class="num">ESS tail</th></tr></thead><tbody>${keyParameters}</tbody></table>
      <h5>PPC statistics</h5><table class="att-table"><thead><tr><th>Statistic</th><th class="num">Observed</th><th class="num">Replications 90%</th><th class="num">p</th></tr></thead><tbody>${ppcRows}</tbody></table></div></div>`;
    const p = state.data.ppc;
    const centres = p.observed.map((_, i) => (p.edges[i] + p.edges[i + 1]) / 2);
    const label = v => (p.scale === FILL_SCALE ? percent(v, 0) : number(10 ** v));
    draw('ppc', {
      grid: {left: 50, right: 16, top: 44, bottom: 44}, legend: {top: 0, data: ['90% of replicated data', 'observed']},
      tooltip: {trigger: 'axis'},
      xAxis: {type: 'category', data: centres.map(label), name: SCALE_LABELS[p.scale] || p.scale, nameLocation: 'middle', nameGap: 28},
      yAxis: {type: 'value', name: 'matches', splitLine: {lineStyle: {color: COLORS.grid}}},
      series: [
        {name: 'lower bound', type: 'line', stack: 'band', silent: true, tooltip: {show: false}, data: p.replicated_q05, lineStyle: {opacity: 0}, symbol: 'none'},
        {name: '90% of replicated data', type: 'line', stack: 'band', data: p.replicated_q95.map((v, i) => v - p.replicated_q05[i]), lineStyle: {opacity: 0}, symbol: 'none', areaStyle: {color: COLORS.primary, opacity: 0.18}},
        {name: 'observed', type: 'bar', data: p.observed, itemStyle: {color: 'rgba(16,40,63,0.55)'}, barCategoryGap: '20%'},
      ],
    });
    if (b.available) {
      const expected = b.pit_histogram.reduce((x, c) => x + c, 0) / b.pit_histogram.length;
      draw('pit', {
        grid: {left: 50, right: 16, top: 20, bottom: 40},
        tooltip: {trigger: 'axis'},
        xAxis: {type: 'category', data: b.pit_histogram.map((_, i) => `${i / 10}–${(i + 1) / 10}`), name: 'PIT', nameLocation: 'middle', nameGap: 26},
        yAxis: {type: 'value', name: 'matches', splitLine: {lineStyle: {color: COLORS.grid}}},
        series: [{type: 'bar', data: b.pit_histogram, itemStyle: {color: COLORS.secondary}, markLine: {silent: true, symbol: 'none', lineStyle: {type: 'dashed', color: COLORS.dark}, label: {formatter: 'perfect calibration', position: 'insideEndTop'}, data: [{yAxis: expected}]}}],
      });
    }
  };

  const quality = () => {
    const q = state.data.quality;
    const items = [
      ['Input records', q.total_records], ['Duplicates removed', q.duplicates_removed], ['Attendance missing (NULL ≠ 0)', q.attendance_unknown],
      ['Zero spectators (behind closed doors)', q.attendance_zero], ['Neutral venue', q.neutral_matches], ['Unknown capacity', q.capacity_unknown],
      ['More spectators than seats', q.capacity_exceeded], ['Suspicious values', q.suspicious_values], ['Outliers (flagged, kept in model)', q.outliers_flagged],
      ['Matches in the spectator-count model', q.usable_count], ['Matches in the fill-rate model', q.usable_fill],
    ];
    const labels = q.issue_labels;
    const examples = q.issues.slice(0, 40).map(i => `<tr><td><a href="${urlFor(urls.urlMatch, i.match_id)}">${i.match_id}</a></td><td>${html(labels[i.code] || i.code)}</td></tr>`).join('');
    element('[data-maf-quality]').innerHTML = `<div class="maf-two"><dl class="maf-kv">${items.map(([label, value]) => `<dt>${html(label)}</dt><dd>${number(value)}</dd>`).join('')}</dl>
      <div><p class="note">The EHF database has no venue capacity, so the models count spectators only and no fill rate is computed. When the engine receives a capacity (for example from a capacity override file), matches whose capacity is inconsistent with attendance are left out of the fill-rate model but stay in the spectator-count model.</p>
      <h5>Example issues</h5><table class="att-table"><thead><tr><th>Match</th><th>Issue</th></tr></thead><tbody>${examples || '<tr><td colspan="2">none</td></tr>'}</tbody></table></div></div>`;
  };

  const trace = async id => {
    const dialog = root.parentElement.querySelector('[data-maf-dialog]');
    const body = dialog.querySelector('[data-maf-dialog-body]');
    body.innerHTML = '<p class="note">Loading…</p>';
    dialog.showModal();
    try {
      const result = await fetchJson(withParams(urlFor(urls.urlClub, id), {model: state.model}));
      const k = result.club;
      const a = k.away;
      const m = result.model;
      const ref = m.reference;
      const sigmaR = m.groups.find(g => g.name === 'opponent')?.sigma;
      const samples = m.sampler.chains * Math.floor(m.sampler.draws / m.sampler.thin_store);
      const formula = m.measure === 'fill'
        ? String.raw`\mathrm{IAF}_j = 100\cdot\frac{\frac{1}{|X_{ref}|}\sum_{i\in X_{ref}} \operatorname{logit}^{-1}\!\big(\eta_i^{(0)} + R_j\big)}{\frac{1}{|X_{ref}|}\sum_{i\in X_{ref}} \operatorname{logit}^{-1}\!\big(\eta_i^{(0)}\big)}`
        : String.raw`\mathrm{IAF}_j = 100\cdot\frac{\frac{1}{|X_{ref}|}\sum_{i} e^{\eta_i^{(0)} + R_j}}{\frac{1}{|X_{ref}|}\sum_{i} e^{\eta_i^{(0)}}} = 100\cdot e^{R_j}`;
      const scale = v => (m.measure === 'fill' ? percent(v, 2) : number(v));
      const measureLabel = m.measure === 'fill' ? 'fill rate' : 'spectators';
      dialog.querySelector('[data-maf-dialog-title]').textContent = `How IAF was computed — ${k.name}`;
      body.innerHTML = `<dl class="maf-kv">
        <dt>Club</dt><dd>${html(k.name)}${k.names_history.length > 1 ? ` <small class="note">(${html(k.names_history.join(', '))})</small>` : ''}</dd>
        <dt>Model / version</dt><dd>${html(m.label)} · ${html(m.version)}</dd><dt>Training date</dt><dd>${new Date(m.trained_at).toLocaleString(LOCALE)}</dd>
        <dt>Matches in model estimation</dt><dd>${number(m.matches_used)} (${html(m.period.from)} – ${html(m.period.to)})</dd>
        <dt>Club matches as opponent</dt><dd>${number(a.matches)} at ${number(a.hosts)} hosts</dd>
        <dt>Reference population X<sub>ref</sub></dt><dd>matches from seasons ${html(ref.seasons.join(', '))}: ${number(ref.matches_sampled)} drawn from ${number(ref.matches_available)} (fixed seed); each with its own host, season, competition and conditions, but with the opponent effect replaced by R<sub>j</sub></dd>
        <dt>Expected ${measureLabel} — typical opponent</dt><dd>${scale(ref.expected.median)} [95%: ${scale(ref.expected.q025)} – ${scale(ref.expected.q975)}]</dd>
        <dt>Expected ${measureLabel} — ${html(k.name)}</dt><dd>${scale(a.club_mean.median)} [95%: ${scale(a.club_mean.q025)} – ${scale(a.club_mean.q975)}]</dd>
      </dl>
      <h4>IAF formula ${infoIcon('iaf')}</h4><div class="maf-formula">${katex(formula)}</div>
      <p class="note">η<sub>i</sub><sup>(0)</sup> = α + H<sub>h(i)</sub> + HS + S + L + x<sub>i</sub><sup>⊤</sup>β — the predictor of match i without the opponent effect. The reference opponent has R = 0 (the mean of all opponent effects, sum-to-zero constraint).</p>
      <h4>1. Illustration on central values (not the computation method)</h4>
      <ol class="maf-steps"><li>Posterior medians: R<sub>j</sub> = ${number(a.effect.median, 4)}, η<sup>(0)</sup> averaged over X<sub>ref</sub>.</li>
      <li>Numerator: ${scale(a.central.club)}; denominator: ${scale(a.central.reference)}.</li>
      <li>100 × ${scale(a.central.club)} / ${scale(a.central.reference)} = <b>${number(a.central.iaf, 1)}</b></li></ol>
      <h4>2. Actual method — posterior distribution ${infoIcon('iaf_posterior')}</h4>
      <ol class="maf-steps"><li>For each of the S = ${number(samples)} stored posterior samples θ<sup>(s)</sup> (NUTS, ${m.sampler.chains} chains) we compute IAF<sub>j</sub><sup>(s)</sup> with the formula above — with the full η<sup>(0,s)</sup> for every reference match. ${infoIcon('monte_carlo')}</li>
      <li>Posterior median: <b>${number(a.iaf.median, 1)}</b>; mean: ${number(a.iaf.mean, 1)}. The median of samples ≠ the formula applied to medians (non-linearity of the logistic function — Jensen's inequality).</li>
      <li>95% credible interval = the 2.5% and 97.5% quantiles of the samples: <b>${number(a.iaf.q025, 1)} – ${number(a.iaf.q975, 1)}</b> ${infoIcon('przedzial')}</li>
      <li>P(IAF &gt; 100 | data) = (1/S) Σ<sub>s</sub> 1[IAF<sup>(s)</sup> &gt; 100] = <b>${percent(a.p_gt_100, 1)}</b> ${infoIcon('p_iaf')}</li>
      ${a.pp ? `<li>Effect in percentage points: ${signed(a.pp.median, 2)} p.p. [${signed(a.pp.q025, 2)}; ${signed(a.pp.q975, 2)}] ${infoIcon('efekt_pp')}</li>` : ''}
      <li>Extra spectators (reference venue${ref.capacity_median ? ` ${number(ref.capacity_median)} seats` : ''}): ${signed(a.extra.median, 0)} [${signed(a.extra.q025, 0)}; ${signed(a.extra.q975, 0)}]</li></ol>
      <h4>Coefficients affecting the result</h4>
      <table class="att-table"><thead><tr><th>Component</th><th class="num">Median</th><th class="num">95%</th><th>Role</th></tr></thead><tbody>
      <tr><td>R<sub>j</sub> — club effect as opponent</td><td class="num">${number(a.effect.median, 4)}</td><td class="num">${number(a.effect.q025, 3)} – ${number(a.effect.q975, 3)}</td><td>the only parameter that differs between numerator and denominator</td></tr>
      <tr><td>σ<sub>R</sub> — spread of opponent effects ${infoIcon('hiperprior')}</td><td class="num">${sigmaR ? number(sigmaR.median, 3) : '—'}</td><td class="num">${sigmaR ? `${number(sigmaR.q025, 3)} – ${number(sigmaR.q975, 3)}` : '—'}</td><td>shrinkage strength (partial pooling) ${infoIcon('pooling')}</td></tr>
      <tr><td>α, H, HS, S, L, β</td><td class="num" colspan="2">through η<sup>(0)</sup> of the reference matches</td><td>shared by all clubs — standardises the comparison</td></tr>
      </tbody></table>
      <dl class="maf-kv"><dt>Club IAF diagnostics</dt><dd>R-hat ${number(a.rhat, 3)} ${infoIcon('rhat')} · ESS ${number(a.ess_bulk)} ${infoIcon('ess')}</dd>
      <dt>Reliability assessment</dt><dd>${a.reliable ? 'reliable' : html(a.notes.join('; '))}</dd></dl>
      <p class="note">The result is a statistical effect associated with the presence of the opponent, controlling for host, season and match conditions — not proof that a given number of spectators came solely because of that opponent.</p>`;
      placeIcons(body);
    } catch (error) {
      body.innerHTML = `<p class="att-warning">${html(error.message)}</p>`;
    }
  };

  const load = async () => {
    state.model = element('[data-maf-model]')?.value;
    if (!state.model || !element('[data-maf-kpis]')) return;
    element('[data-maf-kpis]').innerHTML = '<p class="note">Loading model…</p>';
    try {
      state.data = await fetchJson(withParams(urls.urlData, {model: state.model}));
    } catch (error) {
      element('[data-maf-kpis]').innerHTML = `<p class="att-warning">${html(error.message)}</p>`;
      return;
    }
    state.selected.clear();
    state.limit = ROW_LIMIT;
    const opponents = opponentClubs().sort((a, b) => b.away.matches - a.away.matches);
    const reliableOpponents = opponents.filter(club => club.away.reliable);
    state.trends = (reliableOpponents.length ? reliableOpponents : opponents).slice(0, 3).map(club => club.id);
    const alphabetical = [...opponents].sort((a, b) => a.name.localeCompare(b.name, 'en'));
    element('[data-maf-trend-select]').innerHTML = clubOptions(alphabetical);
    element('[data-maf-posterior-select]').innerHTML = clubOptions(alphabetical, opponents[0]?.id);
    const hosts = state.data.clubs.filter(club => club.home).sort((a, b) => b.home.matches - a.home.matches);
    element('[data-maf-host-select]').innerHTML = clubOptions(hosts, hosts[0]?.id);
    status();
    kpi();
    ranking();
    refreshCompareButton();
    forest();
    trends();
    posterior();
    hostAnalysis();
    prepareSimulator();
    deviations();
    diagnostics();
    quality();
    placeIcons();
  };

  const bind = () => {
    element('[data-maf-model]')?.addEventListener('change', load);
    ['[data-maf-search]', '[data-maf-reliable]', '[data-maf-min]'].forEach(s => element(s)?.addEventListener('input', () => { state.limit = ROW_LIMIT; ranking(); }));
    element('[data-maf-more]')?.addEventListener('click', () => { state.limit += ROW_LIMIT; ranking(); });
    element('[data-maf-ranking]')?.addEventListener('click', event => {
      const header = event.target.closest('th[data-sort]');
      if (header && !event.target.closest('[data-maf-info-button]')) {
        const field = header.dataset.sort;
        state.sorting = {field, direction: state.sorting.field === field ? -state.sorting.direction : (field === 'name' ? 1 : -1)};
        ranking();
        return;
      }
      const checkbox = event.target.closest('[data-maf-select]');
      if (checkbox) {
        const id = Number(checkbox.dataset.mafSelect);
        if (checkbox.checked) {
          if (state.selected.size >= 2) { checkbox.checked = false; return; }
          state.selected.add(id);
        } else state.selected.delete(id);
        refreshCompareButton();
        return;
      }
      const traceButton = event.target.closest('[data-maf-trace]');
      if (traceButton) { trace(Number(traceButton.dataset.mafTrace)); return; }
      if (event.target.closest('a, button, input')) return;
      const row = event.target.closest('tr.maf-row');
      if (row) rowDetails(row);
    });
    element('[data-maf-compare]')?.addEventListener('click', compare);
    ['[data-maf-forest-sort]', '[data-maf-forest-limit]', '[data-maf-forest-reliable]'].forEach(s => element(s)?.addEventListener('change', forest));
    element('[data-maf-trend-add]')?.addEventListener('click', () => {
      const id = Number(element('[data-maf-trend-select]').value);
      if (id && !state.trends.includes(id) && state.trends.length < 6) { state.trends.push(id); trends(); }
    });
    element('[data-maf-trend-chips]')?.addEventListener('click', event => {
      const remove = event.target.closest('[data-maf-trend-remove]');
      if (remove) { state.trends = state.trends.filter(id => id !== Number(remove.dataset.mafTrendRemove)); trends(); }
    });
    element('[data-maf-posterior-select]')?.addEventListener('change', posterior);
    element('[data-maf-host-select]')?.addEventListener('change', hostAnalysis);
    element('[data-maf-sim]')?.addEventListener('submit', event => { event.preventDefault(); simulate(event.target); });
    root.parentElement.querySelector('[data-maf-dialog-close]')?.addEventListener('click', () => root.parentElement.querySelector('[data-maf-dialog]').close());
  };

  const start = () => {
    if (state.started) return;
    state.started = true;
    bind();
    load();
  };
  const visible = () => !panel.hidden && panel.offsetParent !== null;
  if (visible()) start();
  new MutationObserver(() => {
    if (visible()) {
      start();
      state.charts.forEach(chart => chart.resize());
    }
  }).observe(panel, {attributes: true, attributeFilter: ['hidden', 'class', 'style']});
})();
