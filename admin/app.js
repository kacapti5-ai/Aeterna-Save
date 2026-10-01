const TYPE_LABEL = { cards: "卡牌", toys: "玩具", account: "账号", items: "道具/素材" };

let market = { games: [], products: [] };
let site = { stats: {} };

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "请求失败");
  return data;
}

function showApp(on) {
  document.getElementById("loginView").classList.toggle("hidden", on);
  document.getElementById("appView").classList.toggle("hidden", !on);
}

async function boot() {
  try {
    const me = await api("/api/me");
    if (me.ok) {
      showApp(true);
      await loadAll();
    }
  } catch (_) {}
}

document.getElementById("loginBtn").addEventListener("click", async () => {
  const err = document.getElementById("loginError");
  err.classList.add("hidden");
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: document.getElementById("password").value }),
    });
    showApp(true);
    await loadAll();
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove("hidden");
  }
});
document.getElementById("password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("loginBtn").click();
});

document.getElementById("logoutBtn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST", body: "{}" });
  showApp(false);
});

async function loadAll() {
  market = await api("/api/market");
  site = await api("/api/site");
  renderStats();
  renderProducts();
  renderGames();
  document.getElementById("statMonthly").value = (site.stats && site.stats.monthlyCards) || "";
  document.getElementById("statRate").value = (site.stats && site.stats.verifyRate) || "";
  document.getElementById("statGmv").value = (site.stats && site.stats.gmv) || "";
}

function renderStats() {
  const list = market.products || [];
  document.getElementById("statProducts").textContent = list.filter((p) => p.published !== false).length;
  document.getElementById("statGames").textContent = (market.games || []).length;
  document.getElementById("statHidden").textContent = list.filter((p) => p.published === false).length;
}

function renderProducts() {
  const tb = document.getElementById("productTable");
  tb.innerHTML = (market.products || [])
    .map((p) => {
      const on = p.published !== false;
      return `<tr class="border-b border-amber-100">
        <td class="py-2 pr-2">${escapeHtml(p.title || "")}</td>
        <td>${escapeHtml(p.gameName || p.game || "")}</td>
        <td>¥${Number(p.price || 0).toLocaleString()}</td>
        <td>${on ? '<span class="text-green-600">上架</span>' : '<span class="text-slate-400">隐藏</span>'}</td>
        <td class="text-right whitespace-nowrap">
          <button class="text-[#1E58E0] mr-3" data-edit="${p.id}">编辑</button>
          <button class="text-red-500" data-del="${p.id}">删除</button>
        </td>
      </tr>`;
    })
    .join("");
  tb.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => openModal(b.dataset.edit)));
  tb.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => removeProduct(b.dataset.del)));
}

function renderGames() {
  const box = document.getElementById("gameList");
  box.innerHTML = (market.games || [])
    .map(
      (g, i) => `<div class="border rounded-lg p-3 flex gap-2 items-center">
        <input data-g="name" data-i="${i}" class="flex-1 border rounded px-2 py-1 text-sm" value="${escapeAttr(g.name)}">
        <input data-g="offers" data-i="${i}" class="w-20 border rounded px-2 py-1 text-sm" value="${escapeAttr(g.offers)}">
        <input data-g="color" data-i="${i}" class="w-24 border rounded px-2 py-1 text-sm" value="${escapeAttr(g.color)}">
        <button class="text-red-500 text-sm" data-gdel="${i}">删</button>
      </div>`
    )
    .join("");
  box.querySelectorAll("input").forEach((inp) => {
    inp.addEventListener("change", () => {
      const i = Number(inp.dataset.i);
      market.games[i][inp.dataset.g] = inp.value;
    });
  });
  box.querySelectorAll("[data-gdel]").forEach((b) => {
    b.addEventListener("click", async () => {
      market.games.splice(Number(b.dataset.gdel), 1);
      await saveMarket();
    });
  });
}

document.getElementById("addGameBtn").addEventListener("click", async () => {
  const name = prompt("游戏名称");
  if (!name) return;
  market.games.push({
    id: "g" + Date.now(),
    name,
    icon: "fa-star",
    offers: "0",
    color: "#1E58E0",
  });
  await saveMarket();
});

function showPublish(res) {
  const el = document.getElementById("siteMsg");
  el.classList.remove("hidden", "text-green-600", "text-red-500");
  if (res && res.published) {
    el.classList.add("text-green-600");
    el.textContent = "已保存，并正在同步到官网 aeternasave.com（大约 1 分钟后刷新可见）。";
  } else {
    el.classList.add("text-red-500");
    el.textContent = "已保存在服务器，但同步官网失败：" + ((res && res.error) || "未知错误");
  }
}

async function saveMarket() {
  const res = await api("/api/market", { method: "PUT", body: JSON.stringify(market) });
  await loadAll();
  showPublish(res);
}

document.getElementById("saveSiteBtn").addEventListener("click", async () => {
  site.stats = site.stats || {};
  site.stats.monthlyCards = document.getElementById("statMonthly").value;
  site.stats.verifyRate = document.getElementById("statRate").value;
  site.stats.gmv = document.getElementById("statGmv").value;
  const res = await api("/api/site", { method: "PUT", body: JSON.stringify(site) });
  showPublish(res);
});

function openModal(id) {
  const form = document.getElementById("productForm");
  const sel = form.game;
  sel.innerHTML = market.games.map((g) => `<option value="${g.id}">${escapeHtml(g.name)}</option>`).join("");
  const p = id ? market.products.find((x) => x.id === id) : null;
  form.id.value = p ? p.id : "";
  form.title.value = p ? p.title : "";
  form.price.value = p ? p.price : "";
  form.image.value = p ? p.image : "🎴";
  form.game.value = p ? p.game : (market.games[0] && market.games[0].id) || "";
  form.type.value = p ? p.type : "cards";
  form.typeLabel.value = p ? p.typeLabel : "评级卡牌";
  form.server.value = p ? p.server : "";
  form.level.value = p ? p.level : "";
  form.seller.value = p ? p.seller : "云伴认证卖家";
  form.sellerRating.value = p ? p.sellerRating : 5;
  form.sellerOrders.value = p ? p.sellerOrders : 0;
  form.delivery.value = p ? p.delivery : "48小时内";
  form.cardGrade.value = p ? p.cardGrade || "" : "";
  form.tags.value = p && p.tags ? p.tags.join(",") : "";
  form.items.value = p && p.items ? p.items.join("\n") : "";
  form.verifyNote.value = p ? p.verifyNote || "" : "";
  form.published.checked = !p || p.published !== false;
  form.verified.checked = p ? !!p.verified : true;
  form.escrow.checked = p ? !!p.escrow : true;
  form.compensation.checked = p ? !!p.compensation : false;
  form.legacy.checked = p ? !!p.legacy : false;
  form.legacyPlan.value = p ? p.legacyPlan || "" : "";
  document.getElementById("modalTitle").textContent = p ? "编辑商品" : "新增商品";
  document.getElementById("modal").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("modal").classList.add("hidden");
}
document.getElementById("closeModal").onclick = closeModal;
document.getElementById("cancelModal").onclick = closeModal;
document.getElementById("addProductBtn").onclick = () => openModal(null);

document.getElementById("productForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const game = market.games.find((g) => g.id === f.game.value);
  const row = {
    id: f.id.value || "p" + Date.now(),
    game: f.game.value,
    gameName: game ? game.name : f.game.value,
    type: f.type.value,
    typeLabel: f.typeLabel.value || TYPE_LABEL[f.type.value] || f.type.value,
    title: f.title.value,
    price: Number(f.price.value || 0),
    server: f.server.value,
    level: f.level.value,
    seller: f.seller.value,
    sellerRating: Number(f.sellerRating.value || 0),
    sellerOrders: Number(f.sellerOrders.value || 0),
    delivery: f.delivery.value,
    verified: f.verified.checked,
    escrow: f.escrow.checked,
    compensation: f.compensation.checked,
    legacy: f.legacy.checked,
    legacyPlan: f.legacyPlan.value,
    tags: f.tags.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
    image: f.image.value || "🎴",
    items: f.items.value.split(/\n/).map((s) => s.trim()).filter(Boolean),
    linkedAssets: [],
    verifyNote: f.verifyNote.value,
    published: f.published.checked,
  };
  if (f.cardGrade.value) row.cardGrade = f.cardGrade.value;
  const idx = market.products.findIndex((p) => p.id === row.id);
  if (idx >= 0) {
    row.linkedAssets = market.products[idx].linkedAssets || [];
    market.products[idx] = Object.assign({}, market.products[idx], row);
  } else {
    market.products.unshift(row);
  }
  await saveMarket();
  closeModal();
});

async function removeProduct(id) {
  if (!confirm("确定删除这个商品？")) return;
  market.products = market.products.filter((p) => p.id !== id);
  await saveMarket();
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, "&quot;");
}

boot();
