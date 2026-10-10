(() => {
  const root = document.querySelector('[data-mathlib]');
  if (!root) return;

  const COLORS = {primary: '#2b6ea4', secondary: '#3a7c67', accent: '#9f6a15', grid: '#e5eaf0'};
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const renderFormulas = element => {
    if (typeof window.renderMathInElement !== 'function') return;
    window.renderMathInElement(element, {
      delimiters: [
        {left: '\\[', right: '\\]', display: true},
        {left: '\\(', right: '\\)', display: false},
      ],
      throwOnError: false,
      strict: 'ignore',
    });
  };

  const numberEquations = article => {
    const numbers = new Map();
    article.querySelectorAll('.ml-eq[id]').forEach((equation, index) => {
      const number = index + 1;
      numbers.set(equation.id, number);
      const label = document.createElement('span');
      label.className = 'ml-eqnum';
      label.innerHTML = `<a href="#${equation.id}" title="Direct link to the formula">(${number})</a>`;
      equation.append(label);
    });
    article.querySelectorAll('a.ml-eqref').forEach(reference => {
      const target = (reference.getAttribute('href') || '').slice(1);
      if (numbers.has(target)) reference.textContent = `(${numbers.get(target)})`;
    });
  };

  const lgamma = x => {
    const g = 7;
    const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313,
      -176.61503916999185, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6,
      1.5056327351493116e-7];
    if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
    x -= 1;
    let a = c[0];
    const t = x + g + 0.5;
    for (let i = 1; i < g + 2; i += 1) a += c[i] / (x + i);
    return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
  };
  const lbeta = (a, b) => lgamma(a) + lgamma(b) - lgamma(a + b);
  const lchoose = (n, k) => lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1);
  const range = (from, to, steps) => Array.from({length: steps + 1}, (_, i) => from + (to - from) * i / steps);
  const betaDensity = (x, a, b) => (x <= 0 || x >= 1) ? 0 : Math.exp((a - 1) * Math.log(x) + (b - 1) * Math.log(1 - x) - lbeta(a, b));

  const SLIDERS = {
    mu: [-5, 5, 0.1], sigma: [0.1, 5, 0.1], a: [0.2, 30, 0.1], b: [0.2, 30, 0.1],
    phi: [0.5, 100, 0.5], n: [1, 200, 1], p: [0.01, 0.99, 0.01], kappa: [0.2, 50, 0.1],
    alpha: [-5, 5, 0.1], beta: [-4, 4, 0.1], k: [0, 200, 1], tau: [0.05, 2, 0.05],
  };
  const MEAN_SLIDERS = {mu: [0.01, 0.99, 0.01]};

  const PLOT_TYPES = {
    normal: {
      title: p => `N(μ = ${p.mu}, σ = ${p.sigma})`,
      data: p => {
        const xs = range(p.mu - 4 * p.sigma, p.mu + 4 * p.sigma, 200);
        return {continuous: true, series: [{name: 'density', points: xs.map(x => [x, Math.exp(-0.5 * ((x - p.mu) / p.sigma) ** 2) / (p.sigma * Math.sqrt(2 * Math.PI))])}]};
      },
    },
    beta: {
      title: p => `Beta(a = ${p.a}, b = ${p.b}), mean = ${(p.a / (p.a + p.b)).toFixed(3)}`,
      data: p => ({continuous: true, series: [{name: 'density', points: range(0.001, 0.999, 200).map(x => [x, betaDensity(x, p.a, p.b)])}]}),
    },
    'beta-mean': {
      sliders: MEAN_SLIDERS,
      title: p => `Beta(μ = ${p.mu}, φ = ${p.phi}): a = ${(p.mu * p.phi).toFixed(2)}, b = ${((1 - p.mu) * p.phi).toFixed(2)}`,
      data: p => ({continuous: true, series: [{name: 'density', points: range(0.001, 0.999, 200).map(x => [x, betaDensity(x, p.mu * p.phi, (1 - p.mu) * p.phi)])}]}),
    },
    binomial: {
      title: p => `Bin(n = ${p.n}, p = ${p.p})`,
      data: p => ({continuous: false, series: [{name: 'P(X = k)', points: range(0, p.n, p.n).map(k => [k, Math.exp(lchoose(p.n, k) + k * Math.log(p.p) + (p.n - k) * Math.log(1 - p.p))])}]}),
    },
    betabinomial: {
      title: p => `BetaBin(n = ${p.n}, a = ${p.a}, b = ${p.b})`,
      data: p => ({continuous: false, series: [{name: 'P(X = k)', points: range(0, p.n, p.n).map(k => [k, Math.exp(lchoose(p.n, k) + lbeta(k + p.a, p.n - k + p.b) - lbeta(p.a, p.b))])}]}),
    },
    negbinomial: {
      sliders: {mu: [1, 3000, 1]},
      title: p => `NB(μ = ${p.mu}, κ = ${p.kappa}), variance = ${Math.round(p.mu + p.mu * p.mu / p.kappa)}`,
      data: p => {
        const top = Math.ceil(p.mu + 4 * Math.sqrt(p.mu + p.mu * p.mu / p.kappa));
        const step = Math.max(1, Math.floor(top / 300));
        const points = [];
        for (let y = 0; y <= top; y += step) {
          points.push([y, Math.exp(lgamma(y + p.kappa) - lgamma(p.kappa) - lgamma(y + 1) + p.kappa * Math.log(p.kappa / (p.kappa + p.mu)) + y * Math.log(p.mu / (p.kappa + p.mu)))]);
        }
        return {continuous: step > 1, series: [{name: 'P(Y = y)', points}]};
      },
    },
    logistic: {
      title: p => `p(x) = logit⁻¹(${p.alpha} + ${p.beta}·x)`,
      data: p => ({continuous: true, series: [{name: 'p(x)', points: range(-6, 6, 200).map(x => [x, 1 / (1 + Math.exp(-(p.alpha + p.beta * x)))])}]}),
    },
    'beta-update': {
      title: p => `Prior Beta(${p.a}, ${p.b}) → posterior Beta(${p.a + p.k}, ${p.b + Math.max(p.n - p.k, 0)})`,
      data: p => {
        const k = Math.min(p.k, p.n);
        const xs = range(0.001, 0.999, 200);
        return {continuous: true, series: [
          {name: 'prior', points: xs.map(x => [x, betaDensity(x, p.a, p.b)]), dashed: true},
          {name: 'posterior', points: xs.map(x => [x, betaDensity(x, p.a + k, p.b + p.n - k)])},
        ]};
      },
    },
    shrinkage: {
      title: p => `Shrinkage factor B(n) = (σ²/n) / (σ²/n + τ²), τ = ${p.tau}, σ = ${p.sigma}`,
      data: p => ({continuous: true, xAxis: 'number of matches n', yAxis: 'weight of the population mean', series: [{name: 'B(n)', points: range(1, 60, 59).map(n => [n, (p.sigma ** 2 / n) / (p.sigma ** 2 / n + p.tau ** 2)])}]}),
    },
  };

  let loading = null;
  const loadECharts = () => {
    if (window.echarts) return Promise.resolve(window.echarts);
    if (!loading) {
      loading = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = root.dataset.echartsUrl;
        script.onload = () => resolve(window.echarts);
        script.onerror = reject;
        document.head.append(script);
      });
    }
    return loading;
  };

  const chartOptions = (type, params) => {
    const data = type.data(params);
    return {
      animation: !reducedMotion,
      animationDuration: 250,
      title: {text: type.title(params), left: 'center', textStyle: {fontSize: 13, fontWeight: 600, color: '#173752'}},
      grid: {left: 54, right: 18, top: 40, bottom: 40},
      tooltip: {trigger: 'axis', valueFormatter: v => Number(v).toPrecision(4)},
      legend: data.series.length > 1 ? {bottom: 0} : undefined,
      xAxis: {type: 'value', name: data.xAxis || '', nameLocation: 'middle', nameGap: 26, scale: true, splitLine: {lineStyle: {color: COLORS.grid}}},
      yAxis: {type: 'value', name: data.yAxis || '', splitLine: {lineStyle: {color: COLORS.grid}}},
      series: data.series.map((item, index) => data.continuous ? {
        name: item.name, type: 'line', showSymbol: false, data: item.points, smooth: false,
        lineStyle: {width: 2, type: item.dashed ? 'dashed' : 'solid', color: index ? COLORS.secondary : COLORS.primary},
        areaStyle: item.dashed ? undefined : {opacity: 0.12, color: index ? COLORS.secondary : COLORS.primary},
      } : {name: item.name, type: 'bar', data: item.points, barMaxWidth: 14, itemStyle: {color: COLORS.primary}}),
    };
  };

  const buildPlot = async host => {
    const type = PLOT_TYPES[host.dataset.plot];
    if (!type) return;
    let params = {};
    try { params = JSON.parse(host.dataset.params || '{}'); } catch (error) { params = {}; }
    const box = document.createElement('div');
    box.className = 'ml-plot-box';
    const canvas = document.createElement('div');
    canvas.className = 'ml-plot-canvas';
    canvas.setAttribute('role', 'img');
    const controls = document.createElement('div');
    controls.className = 'ml-plot-controls';
    box.append(canvas, controls);
    host.replaceChildren(box);
    const echarts = await loadECharts();
    const chart = echarts.init(canvas, null, {renderer: 'svg'});
    const refresh = () => {
      canvas.setAttribute('aria-label', `Chart: ${type.title(params)}`);
      chart.setOption(chartOptions(type, params), true);
    };
    Object.keys(params).forEach(name => {
      const [min, max, step] = (type.sliders && type.sliders[name]) || SLIDERS[name] || [0, 10, 0.1];
      const label = document.createElement('label');
      const input = document.createElement('input');
      Object.assign(input, {type: 'range', min, max, step, value: params[name]});
      const output = document.createElement('output');
      output.value = params[name];
      input.addEventListener('input', () => {
        params[name] = Number(input.value);
        output.value = input.value;
        refresh();
      });
      label.append(document.createTextNode(name), input, output);
      controls.append(label);
    });
    refresh();
    window.addEventListener('resize', () => chart.resize());
  };

  const tableOfContents = () => {
    const links = [...document.querySelectorAll('[data-ml-toc]')];
    if (!links.length || !('IntersectionObserver' in window)) return;
    const map = new Map(links.map(link => [link.dataset.mlToc, link]));
    const observer = new IntersectionObserver(entries => {
      entries.filter(entry => entry.isIntersecting).forEach(entry => {
        links.forEach(link => link.classList.remove('active'));
        map.get(entry.target.id)?.classList.add('active');
      });
    }, {rootMargin: '0px 0px -70% 0px'});
    map.forEach((_, id) => {
      const target = document.getElementById(id);
      if (target) observer.observe(target);
    });
  };

  const search = () => {
    const input = document.querySelector('[data-ml-search]');
    if (!input) return;
    input.addEventListener('input', () => {
      const phrase = input.value.trim().toLowerCase();
      document.querySelectorAll('[data-ml-item]').forEach(element => {
        element.hidden = Boolean(phrase) && !element.dataset.mlItem.includes(phrase);
      });
      document.querySelectorAll('[data-ml-category]').forEach(category => {
        const visible = category.querySelectorAll('[data-ml-item]:not([hidden])').length;
        category.hidden = Boolean(phrase) && visible === 0;
      });
    });
  };

  const article = document.querySelector('[data-ml-article]');
  if (article) {
    numberEquations(article);
    renderFormulas(article);
    article.querySelectorAll('.ml-plot[data-plot]').forEach(host => { buildPlot(host); });
    tableOfContents();
    if (window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
  }
  renderFormulas(document.querySelector('.ml-main') || root);
  search();
})();
