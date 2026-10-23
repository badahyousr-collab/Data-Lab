const rub = cents => new Intl.NumberFormat('ru-RU', {style:'currency', currency:'RUB', maximumFractionDigits:2}).format(cents / 100);
const number = value => new Intl.NumberFormat('ru-RU').format(value);
const byId = id => document.getElementById(id);
const svgNS = 'http://www.w3.org/2000/svg';
const svgNode = (name, attrs = {}) => {
  const el = document.createElementNS(svgNS, name);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
  return el;
};
const toDay = value => new Date(`${value}T00:00:00Z`);
const isoDay = value => value.toISOString().slice(0, 10);
const addDays = (value, days) => new Date(value.getTime() + days * 86400000);

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const button = byId('theme-toggle');
  button.textContent = theme === 'dark' ? 'Светлая тема' : 'Тёмная тема';
  button.setAttribute('aria-label', `Включить ${theme === 'dark' ? 'светлую' : 'тёмную'} тему`);
  const meta = document.querySelector('meta[name="theme-color"]');
  meta.content = theme === 'dark' ? '#111111' : '#ffffff';
  try { localStorage.setItem('data-lab-theme', theme); } catch (_) {}
}

function trendRows(rows) {
  const choice = byId('trend-range').value;
  const custom = byId('trend-custom');
  custom.hidden = choice !== 'custom';
  const error = byId('trend-error');
  const from = byId('trend-from').value, to = byId('trend-to').value;
  const invalid = choice === 'custom' && from && to && from > to;
  error.hidden = !invalid;
  error.textContent = invalid ? 'Начальная дата позже конечной' : '';
  if (invalid || !rows.length) return [];
  if (choice === 'custom') return rows.filter(row => (!from || row.ordered_at >= from) && (!to || row.ordered_at <= to));
  if (choice === 'all') return rows;
  const latest = rows.reduce((max, row) => row.ordered_at > max ? row.ordered_at : max, rows[0].ordered_at);
  const start = isoDay(addDays(toDay(latest), 1 - Number(choice)));
  return rows.filter(row => row.ordered_at >= start);
}

function bucketFor(day, unit) {
  if (unit === 'month') return day.slice(0, 7);
  if (unit === 'day') return day;
  const d = toDay(day);
  const weekday = (d.getUTCDay() + 6) % 7;
  return isoDay(addDays(d, -weekday));
}

function nextBucket(key, unit) {
  if (unit === 'month') {
    const d = toDay(`${key}-01`);
    d.setUTCMonth(d.getUTCMonth() + 1);
    return d.toISOString().slice(0, 7);
  }
  return isoDay(addDays(toDay(key), unit === 'week' ? 7 : 1));
}

function renderTrend(rows) {
  const container = byId('trend-chart');
  container.replaceChildren();
  const selected = trendRows(rows);
  if (!selected.length) {
    container.textContent = 'Нет данных за выбранный период';
    container.classList.add('empty');
    container.setAttribute('aria-label', 'Нет данных за выбранный период');
    return;
  }
  container.classList.remove('empty');
  const dates = selected.map(row => row.ordered_at).sort();
  const span = Math.round((toDay(dates.at(-1)) - toDay(dates[0])) / 86400000) + 1;
  const unit = span <= 45 ? 'day' : span <= 120 ? 'week' : 'month';
  const sums = new Map();
  selected.forEach(row => {
    const key = bucketFor(row.ordered_at, unit);
    sums.set(key, (sums.get(key) || 0) + row.gross_cents - row.refund_cents);
  });
  const entries = [];
  let key = bucketFor(dates[0], unit), last = bucketFor(dates.at(-1), unit);
  while (key <= last && entries.length < 400) {
    entries.push([key, sums.get(key) || 0]);
    key = nextBucket(key, unit);
  }
  const max = Math.max(...entries.map(([, value]) => value), 1);
  const w = 760, h = 240, left = 60, right = 15, top = 18, bottom = 39;
  const plotWidth = w - left - right, plotHeight = h - top - bottom;
  const x = i => left + (entries.length === 1 ? plotWidth / 2 : i * plotWidth / (entries.length - 1));
  const y = value => top + plotHeight - value / max * plotHeight;
  const svg = svgNode('svg', {viewBox:`0 0 ${w} ${h}`, preserveAspectRatio:'none'});
  [0, .5, 1].forEach(fraction => {
    const yy = y(max * fraction);
    svg.append(svgNode('line', {x1:left, y1:yy, x2:w-right, y2:yy, class:'grid-line'}));
    const label = svgNode('text', {x:0, y:yy+4, class:'chart-label'});
    label.textContent = number(Math.round(max * fraction / 100)) + ' ₽';
    svg.append(label);
  });
  const points = entries.map(([, value], i) => `${x(i)},${y(value)}`).join(' ');
  svg.append(svgNode('polyline', {points, class:'chart-line'}));
  const step = Math.max(1, Math.ceil(entries.length / 7));
  entries.forEach(([date, value], i) => {
    if (i % step !== 0 && i !== entries.length - 1) return;
    const dot = svgNode('circle', {cx:x(i), cy:y(value), r:3, class:'chart-dot'});
    const title = svgNode('title');
    title.textContent = `${date}: ${rub(value)}`;
    dot.append(title);
    svg.append(dot);
    const label = svgNode('text', {x:x(i), y:h-10, 'text-anchor':'middle', class:'chart-label'});
    label.textContent = unit === 'month' ? date.slice(5) + '.' + date.slice(2, 4) : date.slice(5);
    svg.append(label);
  });
  container.setAttribute('aria-label', `Выручка, ${unit === 'day' ? 'по дням' : unit === 'week' ? 'по неделям' : 'по месяцам'}, с ${dates[0]} по ${dates.at(-1)}`);
  container.append(svg);
}

function renderProducts(rows) {
  const container = byId('product-chart');
  container.replaceChildren();
  const products = new Map();
  rows.forEach(row => products.set(row.name, (products.get(row.name) || 0) + row.gross_units - row.refunded_units));
  const entries = [...products.entries()].sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    container.textContent = 'Нет товаров за выбранный период';
    container.classList.add('empty');
    return;
  }
  container.classList.remove('empty');
  const max = Math.max(...entries.map(([, units]) => units), 1);
  entries.forEach(([name, units]) => {
    const row = document.createElement('div'); row.className = 'product-row';
    const head = document.createElement('header');
    const label = document.createElement('span'); label.textContent = name;
    const amount = document.createElement('span'); amount.textContent = number(units);
    head.append(label, amount);
    const track = document.createElement('div'); track.className = 'track';
    const fill = document.createElement('div'); fill.className = 'fill'; fill.style.width = `${units / max * 100}%`;
    track.append(fill); row.append(head, track); container.append(row);
  });
}

let reportRows = [];
function render() {
  const category = byId('category').value, from = byId('from-date').value, to = byId('to-date').value;
  const error = byId('filter-error');
  error.hidden = !from || !to || from <= to;
  error.textContent = error.hidden ? '' : 'Начальная дата позже конечной';
  const rows = error.hidden ? reportRows.filter(row =>
    (!from || row.ordered_at >= from) && (!to || row.ordered_at <= to) && (!category || row.category === category)) : [];
  const orders = new Map(), customers = new Map();
  let gross = 0, refunds = 0;
  rows.forEach(row => {
    gross += row.gross_cents; refunds += row.refund_cents;
    const order = orders.get(row.order_id) || {customer:row.customer_id, net:0};
    order.net += row.gross_cents - row.refund_cents;
    orders.set(row.order_id, order);
  });
  let purchases = 0;
  orders.forEach(order => {
    if (order.net > 0) {
      purchases++;
      customers.set(order.customer, (customers.get(order.customer) || 0) + 1);
    }
  });
  byId('revenue').textContent = rub(gross - refunds);
  byId('average').textContent = rub(purchases ? (gross - refunds) / purchases : 0);
  byId('purchases').textContent = number(purchases);
  byId('repeat').textContent = number([...customers.values()].filter(count => count >= 2).length);
  renderTrend(rows);
  renderProducts(rows);
}

setTheme(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
byId('theme-toggle').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
byId('expand-trend').addEventListener('click', () => {
  const panel = byId('trend-panel');
  const expanded = panel.classList.toggle('expanded');
  byId('expand-trend').textContent = expanded ? 'Свернуть график' : 'Развернуть график';
  byId('expand-trend').setAttribute('aria-expanded', String(expanded));
});
['trend-range', 'trend-from', 'trend-to'].forEach(id => byId(id).addEventListener('change', render));
['from-date', 'to-date', 'category'].forEach(id => byId(id).addEventListener('change', render));
byId('reset').addEventListener('click', () => {
  byId('from-date').value = '';
  byId('to-date').value = '';
  byId('category').value = '';
  byId('trend-range').value = 'all';
  byId('trend-from').value = '';
  byId('trend-to').value = '';
  render();
});
fetch('data.json').then(response => {
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}).then(data => {
  if (!data.synthetic || !Array.isArray(data.rows)) throw new Error('Неверный формат данных');
  reportRows = data.rows;
  [...new Set(reportRows.map(row => row.category))].sort().forEach(category => {
    const option = document.createElement('option');
    option.value = category; option.textContent = category;
    byId('category').append(option);
  });
  render();
}).catch(error => {
  const message = byId('load-error');
  message.hidden = false;
  message.textContent = `Не удалось загрузить данные: ${error.message}`;
});
