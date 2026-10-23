const rub = cents => new Intl.NumberFormat('ru-RU', {style:'currency', currency:'RUB', maximumFractionDigits:2}).format(cents / 100);
const number = value => new Intl.NumberFormat('ru-RU').format(value);
const byId = id => document.getElementById(id);
const svgNS = 'http://www.w3.org/2000/svg';
const svgNode = (name, attrs={}) => {
  const el = document.createElementNS(svgNS, name);
  Object.entries(attrs).forEach(([key,value]) => el.setAttribute(key,String(value)));
  return el;
};

function renderTrend(rows) {
  const container = byId('trend-chart'); container.replaceChildren();
  const months = new Map();
  rows.forEach(row => {const month = row.ordered_at.slice(0,7); months.set(month,(months.get(month)||0)+row.gross_cents-row.refund_cents)});
  if (!months.size) {container.textContent='Нет данных за выбранный период';container.className='chart empty';return;}
  container.className='chart';
  const entries = [...months.entries()].sort(([a],[b])=>a.localeCompare(b));
  const max = Math.max(...entries.map(([,v])=>v),1), w=600,h=215,left=42,right=16,top=12,bottom=34;
  const width=w-left-right,height=h-top-bottom;
  const x=i=>left+(entries.length===1?width/2:i*width/(entries.length-1));
  const y=v=>top+height-v/max*height;
  const svg=svgNode('svg',{viewBox:`0 0 ${w} ${h}`,preserveAspectRatio:'none'});
  const defs=svgNode('defs'), gradient=svgNode('linearGradient',{id:'trend-fill',x1:'0',x2:'0',y1:'0',y2:'1'});
  gradient.append(svgNode('stop',{offset:'0%', 'stop-color':'#a99af2','stop-opacity':'.35'}),svgNode('stop',{offset:'100%','stop-color':'#a99af2','stop-opacity':'0'}));defs.append(gradient);svg.append(defs);
  [0,.5,1].forEach(f=>{let yy=y(max*f);svg.append(svgNode('line',{x1:left,y1:yy,x2:w-right,y2:yy,class:'grid-line'}));const label=svgNode('text',{x:0,y:yy+4,class:'chart-label'});label.textContent=number(Math.round(max*f/1000))+'k';svg.append(label)});
  let points=entries.map(([,v],i)=>`${x(i)},${y(v)}`).join(' ');
  const area=`M ${x(0)} ${top+height} `+entries.map(([,v],i)=>`L ${x(i)} ${y(v)}`).join(' ')+` L ${x(entries.length-1)} ${top+height} Z`;
  svg.append(svgNode('path',{d:area,class:'trend-area'}),svgNode('polyline',{points,class:'trend-line'}));
  entries.forEach(([month,v],i)=>{let dot=svgNode('circle',{cx:x(i),cy:y(v),r:4,fill:'#c8bbff'});let title=svgNode('title');title.textContent=`${month}: ${rub(v)}`;dot.append(title);svg.append(dot);let label=svgNode('text',{x:x(i),y:h-9,'text-anchor':'middle',class:'chart-label'});label.textContent=new Date(month+'-01T00:00:00Z').toLocaleDateString('ru-RU',{month:'short'});svg.append(label)});
  container.append(svg);
}

function renderProducts(rows) {
  const container=byId('product-chart');container.replaceChildren();
  const products=new Map();rows.forEach(row=>products.set(row.name,(products.get(row.name)||0)+row.gross_units-row.refunded_units));
  const entries=[...products.entries()].sort((a,b)=>b[1]-a[1]);
  if (!entries.length) {container.textContent='Нет товаров за выбранный период';container.className='product-chart empty';return;}
  container.className='product-chart';const max=Math.max(...entries.map(([,v])=>v),1);
  entries.forEach(([name,units])=>{const row=document.createElement('div');row.className='product-row';const head=document.createElement('header');const label=document.createElement('span');label.textContent=name;const amount=document.createElement('span');amount.textContent=number(units);head.append(label,amount);const track=document.createElement('div');track.className='track';const fill=document.createElement('div');fill.className='fill';fill.style.width=`${units/max*100}%`;track.append(fill);row.append(head,track);container.append(row)});
}

function render(rows) {
  const category=byId('category').value, from=byId('from-date').value,to=byId('to-date').value;
  const error=byId('filter-error');error.hidden=!from||!to||from<=to;error.textContent=error.hidden?'':'Начальная дата позже конечной';
  const selected=error.hidden?rows.filter(row=>(!from||row.ordered_at>=from)&&(!to||row.ordered_at<=to)&&(!category||row.category===category)):[];
  const orders=new Map(),customers=new Map();let gross=0,refunds=0;
  selected.forEach(row=>{gross+=row.gross_cents;refunds+=row.refund_cents;const net=row.gross_cents-row.refund_cents;const order=orders.get(row.order_id)||{customer:row.customer_id,net:0};order.net+=net;orders.set(row.order_id,order)});
  let purchases=0;orders.forEach(order=>{if(order.net>0){purchases++;customers.set(order.customer,(customers.get(order.customer)||0)+1)}});
  byId('revenue').textContent=rub(gross-refunds);byId('average').textContent=purchases?rub((gross-refunds)/purchases):rub(0);
  byId('purchases').textContent=number(purchases);byId('repeat').textContent=number([...customers.values()].filter(count=>count>=2).length);
  byId('row-count').textContent=`${number(orders.size)} оплаченных заказов в срезе`;
  renderTrend(selected);renderProducts(selected);
}

fetch('data.json').then(response=>{if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json()}).then(data=>{
  if(!data.synthetic||!Array.isArray(data.rows))throw new Error('Неверный формат данных');
  const rows=data.rows;const categories=[...new Set(rows.map(row=>row.category))].sort();
  categories.forEach(category=>{const option=document.createElement('option');option.value=category;option.textContent=category;byId('category').append(option)});
  ['from-date','to-date','category'].forEach(id=>byId(id).addEventListener('change',()=>render(rows)));
  byId('reset').addEventListener('click',()=>{byId('from-date').value='';byId('to-date').value='';byId('category').value='';render(rows)});
  render(rows);
}).catch(error=>{const message=byId('filter-error');message.hidden=false;message.textContent=`Не удалось загрузить демонстрационные данные: ${error.message}`});
