let MARKET_GAMES = [];
let MARKET_PRODUCTS = [];
let SITE_SETTINGS = {
  stats: { monthlyCards: "1,240+", verifyRate: "99.6%", gmv: "¥2.8亿+" },
};

function getDataUrl(fileName) {
  const scripts = document.getElementsByTagName("script");
  for (let i = scripts.length - 1; i >= 0; i--) {
    const src = scripts[i].src || "";
    if (src.includes("data.js")) {
      return new URL("../data/" + fileName, src).href;
    }
  }
  return "../data/" + fileName;
}

const marketReady = Promise.all([
  fetch(getDataUrl("market.json"), { cache: "no-store" }).then((r) => {
    if (!r.ok) throw new Error("market.json");
    return r.json();
  }),
  fetch(getDataUrl("site.json"), { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({})),
])
  .then(([market, site]) => {
    MARKET_GAMES = market.games || [];
    MARKET_PRODUCTS = (market.products || []).filter((p) => p.published !== false);
    SITE_SETTINGS = Object.assign(SITE_SETTINGS, site || {});
  })
  .catch((err) => {
    console.error("市场数据加载失败", err);
  });

function getProduct(id) {
  return MARKET_PRODUCTS.find((p) => p.id === id);
}

function filterProducts(filters = {}) {
  return MARKET_PRODUCTS.filter((p) => {
    if (filters.game && filters.game !== "all" && p.game !== filters.game) return false;
    if (filters.type && filters.type !== "all" && p.type !== filters.type) return false;
    if (filters.legacy === "yes" && !p.legacy) return false;
    if (filters.minPrice && p.price < Number(filters.minPrice)) return false;
    if (filters.maxPrice && p.price > Number(filters.maxPrice)) return false;
    if (filters.q) {
      const q = filters.q.toLowerCase();
      if (!p.title.toLowerCase().includes(q) && !p.gameName.includes(filters.q)) return false;
    }
    return true;
  });
}
