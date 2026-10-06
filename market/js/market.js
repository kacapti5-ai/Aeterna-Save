function renderMarketHeader(active) {
  const links = [
    { href: 'index.html', label: '市场首页', key: 'home' },
    { href: 'browse.html?type=cards', label: '卡牌', key: 'cards' },
    { href: 'browse.html?type=toys', label: '实体玩具', key: 'toys' },
    { href: 'browse.html', label: '全部商品', key: 'browse' },
    { href: 'sell.html', label: '我要卖', key: 'sell' },
    { href: '../index.html#collectibles', label: '收藏指南', key: 'guide' },
  ];
  const nav = links.map(l =>
    `<a href="${l.href}" class="${active === l.key ? 'text-[#3B4CCA] font-semibold' : 'text-slate-600 hover:text-[#3B4CCA]'} transition">${l.label}</a>`
  ).join('');

  return `
  <header class="market-header fixed w-full z-50">
    <div class="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
      <a href="index.html" class="flex items-center gap-2 font-bold text-lg text-[#1D355C]">
        <img src="../static/img/logo-mark.png" alt="Aeterna Save" class="h-10 w-auto object-contain bg-white">
        <span>Aeterna Save <span class="text-slate-400 font-normal text-sm hidden sm:inline">· 永恒守护</span></span>
      </a>
      <nav class="hidden lg:flex gap-5 text-sm">${nav}</nav>
      <div class="flex items-center gap-2">
        <span id="sellerNav" class="hidden sm:flex items-center gap-3"></span>
        <a href="browse.html?type=cards" class="btn-g2g px-4 py-2 text-sm hidden sm:inline">买卡牌</a>
        <a href="sell.html" class="btn-outline-g2g px-4 py-2 text-sm hidden sm:inline">我要卖</a>
        <button type="button" id="mMenuBtn" class="lg:hidden text-xl text-[#1D355C] p-2"><i class="fa fa-bars"></i></button>
      </div>
    </div>
    <div id="mMobileMenu" class="hidden lg:hidden border-t border-amber-200 px-4 py-3 flex flex-col gap-2 text-sm bg-white">
      ${links.map(l => `<a href="${l.href}" class="py-2 text-slate-600">${l.label}</a>`).join('')}
      <div id="sellerNavMobile" class="py-2 flex flex-wrap gap-3"></div>
    </div>
  </header>`;
}

function renderProductCard(p) {
  const badges = [];
  if (p.type === 'cards') badges.push('<span class="badge-card text-xs px-2 py-0.5 rounded">TCG卡牌</span>');
  if (p.type === 'toys') badges.push('<span class="badge-toy text-xs px-2 py-0.5 rounded">实体玩具</span>');
  if (p.verified) badges.push('<span class="badge-verified text-xs px-2 py-0.5 rounded">验真</span>');
  if (p.escrow) badges.push('<span class="badge-escrow text-xs px-2 py-0.5 rounded">托管</span>');
  if (p.compensation) badges.push('<span class="badge-compensation text-xs px-2 py-0.5 rounded">110%包赔</span>');
  if (p.legacy) badges.push('<span class="badge-legacy text-xs px-2 py-0.5 rounded">安心计划</span>');

  const thumbClass = (p.type === 'cards') ? 'product-thumb card-thumb' : 'product-thumb';
  const priceColor = p.price >= 10000 ? 'text-[#E3350D]' : 'text-[#3B4CCA]';

  return `
  <a href="product.html?id=${p.id}" class="market-card block overflow-hidden group">
    <div class="${thumbClass} flex items-center justify-center text-5xl">${p.image}</div>
    <div class="p-4">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-xs text-slate-500">${p.gameName}</span>
        <span class="text-xs text-[#3B4CCA] font-medium">${p.typeLabel}</span>
      </div>
      <h3 class="text-sm font-medium text-[#1D355C] line-clamp-2 mb-2 group-hover:text-[#3B4CCA] transition">${p.title}</h3>
      <p class="text-xs text-slate-500 mb-3">${p.server}${p.cardGrade ? ' · ' + p.cardGrade : ''}</p>
      <div class="flex flex-wrap gap-1 mb-3">${badges.join('')}</div>
      <div class="flex justify-between items-end">
        <div>
          <span class="${priceColor} text-xl font-bold">¥${p.price.toLocaleString()}</span>
          <p class="text-xs text-slate-500 mt-1"><i class="fa fa-clock-o mr-1"></i>${p.delivery}</p>
        </div>
        <div class="text-right text-xs text-slate-500">
          <div><i class="fa fa-star text-[#FFCB05]"></i> ${p.sellerRating}</div>
          <div>${p.sellerOrders} 笔成交</div>
        </div>
      </div>
    </div>
  </a>`;
}

function renderTrustSection() {
  return `
  <section class="py-16 border-t border-amber-200 bg-white">
    <div class="max-w-7xl mx-auto px-4">
      <h2 class="text-2xl md:text-3xl font-bold text-center mb-3 text-[#1D355C]">卡牌 & 资产 · 交易安心，收藏也省心</h2>
      <p class="text-slate-500 text-center mb-10 max-w-2xl mx-auto">PSA/BGS 验卡、正版玩具溯源、游戏账号验号——像给收藏买保险，轻松不焦虑</p>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div class="market-card p-6">
          <div class="trust-icon bg-[#FFCB05]/30 text-[#1D355C] mb-4"><i class="fa fa-certificate"></i></div>
          <h4 class="font-bold mb-2 text-[#1D355C]">评级卡牌验真</h4>
          <p class="text-sm text-slate-500">PSA / BGS 官网可查，高值卡显微镜验卡 + 开箱录像</p>
        </div>
        <div class="market-card p-6">
          <div class="trust-icon bg-blue-100 text-[#3B4CCA] mb-4"><i class="fa fa-lock"></i></div>
          <h4 class="font-bold mb-2 text-[#1D355C]">资金 Escrow 托管</h4>
          <p class="text-sm text-slate-500">买家付款后资金锁定，确认收货再放款</p>
        </div>
        <div class="market-card p-6">
          <div class="trust-icon bg-green-100 text-green-700 mb-4"><i class="fa fa-gift"></i></div>
          <h4 class="font-bold mb-2 text-[#1D355C]">实体玩具溯源</h4>
          <p class="text-sm text-slate-500">吊牌防伪、品相报告，正版授权链路可查</p>
        </div>
        <div class="market-card p-6">
          <div class="trust-icon bg-purple-100 text-purple-700 mb-4"><i class="fa fa-heart"></i></div>
          <h4 class="font-bold mb-2 text-[#1D355C]">安心计划 · 有记录</h4>
          <p class="text-sm text-slate-500">高值卡牌与收藏登记后，未来可查完整交易依据</p>
        </div>
      </div>
      <div class="mt-10 legacy-banner rounded-xl p-6 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h4 class="font-bold text-[#3B4CCA] mb-1"><i class="fa fa-list-alt mr-2"></i>卡牌越值钱，记录越重要</h4>
          <p class="text-sm text-slate-500">在本平台买卖的卡牌、玩具、账号均有<strong>永久交易记录</strong>——未来交接像查保单一样清楚。</p>
        </div>
        <a href="../index.html#legacy-guarantee" class="btn-outline-g2g px-6 py-3 text-sm whitespace-nowrap">安心保障说明</a>
      </div>
      <div class="mt-6 rounded-2xl border-2 border-[#FFCB05] bg-[#FFFBEB] p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h4 class="font-bold text-[#1D355C] mb-1"><i class="fa fa-institution mr-2 text-[#3B4CCA]"></i>香港保险 · 高值卡牌自愿加保</h4>
          <p class="text-sm text-slate-600">数字资产安心计划可搭配香港保险机构专项方案，高罕卡牌多买一份保险，心里更踏实。</p>
        </div>
        <a href="../index.html#legacy-guarantee" class="btn-g2g px-6 py-3 text-sm whitespace-nowrap">了解投保</a>
      </div>
      <div class="mt-8 grid grid-cols-3 gap-4 text-center text-sm">
        <div class="market-card p-4">
          <div class="text-2xl font-bold text-[#3B4CCA]">${(SITE_SETTINGS.stats && SITE_SETTINGS.stats.monthlyCards) || "1,240+"}</div>
          <div class="text-slate-500 mt-1">本月卡牌成交</div>
        </div>
        <div class="market-card p-4">
          <div class="text-2xl font-bold text-[#FFCB05]">${(SITE_SETTINGS.stats && SITE_SETTINGS.stats.verifyRate) || "99.6%"}</div>
          <div class="text-slate-500 mt-1">验卡通过率</div>
        </div>
        <div class="market-card p-4">
          <div class="text-2xl font-bold text-[#E3350D]">${(SITE_SETTINGS.stats && SITE_SETTINGS.stats.gmv) || "¥2.8亿+"}</div>
          <div class="text-slate-500 mt-1">平台卡牌交易额</div>
        </div>
      </div>
    </div>
  </section>`;
}

function initMobileMenu() {
  const btn = document.getElementById('mMenuBtn');
  const menu = document.getElementById('mMobileMenu');
  if (btn && menu) {
    btn.addEventListener('click', () => menu.classList.toggle('hidden'));
  }
}

document.addEventListener('DOMContentLoaded', initMobileMenu);
