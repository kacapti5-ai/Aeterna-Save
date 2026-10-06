const AETERNA_API = (function () {
  const host = location.hostname;
  const port = location.port;
  if (port === "8787" || port === "8788" || host === "121.41.104.180") return "";
  return "http://121.41.104.180:8788";
})();

const SELLER_TOKEN_KEY = "aeterna_seller_token";

function sellerToken() {
  try {
    return localStorage.getItem(SELLER_TOKEN_KEY) || "";
  } catch (_) {
    return "";
  }
}

function setSellerToken(token) {
  try {
    if (token) localStorage.setItem(SELLER_TOKEN_KEY, token);
    else localStorage.removeItem(SELLER_TOKEN_KEY);
  } catch (_) {}
}

async function sellerApi(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const token = sellerToken();
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch(AETERNA_API + path, {
    ...opts,
    headers,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "请求失败");
  return data;
}

async function sellerMe() {
  if (!sellerToken()) return null;
  try {
    const data = await sellerApi("/api/seller/me");
    return data.ok ? data.user : null;
  } catch (_) {
    return null;
  }
}

function authLinksHtml(user, active) {
  if (user) {
    return `
      <a href="mine.html" class="${active === "mine" ? "text-[#3B4CCA] font-semibold" : "text-slate-600"} text-sm">${escapeText(user.name)}</a>
      <button type="button" id="sellerLogout" class="text-sm text-slate-400 hover:text-red-500">退出</button>
    `;
  }
  return `
    <a href="login.html" class="text-sm text-slate-600 hover:text-[#3B4CCA]">登录</a>
    <a href="register.html" class="btn-outline-g2g px-3 py-1.5 text-sm">注册上架</a>
  `;
}

function escapeText(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function mountSellerNav(active) {
  const slot = document.getElementById("sellerNav");
  const mobile = document.getElementById("sellerNavMobile");
  const user = await sellerMe();
  const html = authLinksHtml(user, active);
  if (slot) slot.innerHTML = html;
  if (mobile) mobile.innerHTML = html;
  document.querySelectorAll("#sellerLogout").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await sellerApi("/api/seller/logout", { method: "POST", body: "{}" });
      } catch (_) {}
      setSellerToken("");
      location.href = "login.html";
    });
  });
  return user;
}

function requireSeller(user, next) {
  if (user) return true;
  const dest = encodeURIComponent(next || location.pathname.split("/").pop() || "sell.html");
  location.href = "login.html?next=" + dest;
  return false;
}
