const AETERNA_API = (function () {
  const host = location.hostname;
  const port = location.port;
  if (port === "8787" || port === "8788" || host === "121.41.104.180") return "";
  return "http://121.41.104.180";
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
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  let res;
  try {
    res = await fetch(AETERNA_API + path, {
      ...opts,
      headers,
      signal: ctrl.signal,
    });
  } catch (e) {
    throw new Error("连不上上架服务，请刷新后重试");
  } finally {
    clearTimeout(timer);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "请求失败");
  return data;
}

function bounceToShopHost() {
  const h = location.hostname;
  if (h === "aeternasave.com" || h === "www.aeternasave.com") {
    location.replace("http://121.41.104.180" + location.pathname + location.search);
    return true;
  }
  return false;
}

function composeAccountLogin(form) {
  const mode = (form.accountType && form.accountType.value) || "email";
  const raw = (form.login.value || "").trim();
  if (mode === "email") return raw;
  let dial = mode === "other" ? (form.dialOther.value || "").trim().replace(/^\+/, "") : mode;
  dial = dial.replace(/\D/g, "");
  let num = raw.replace(/[\s\-()]/g, "");
  if (num.startsWith("00")) num = num.slice(2);
  if (num.startsWith("+")) return "+" + num.replace(/\D/g, "");
  if (dial === "86" && /^1[3-9]\d{9}$/.test(num)) return "+86" + num;
  num = num.replace(/^0+/, "");
  return "+" + dial + num.replace(/\D/g, "");
}

function bindAccountTypeToggle(form) {
  const type = form.accountType;
  const other = form.dialOther;
  const login = form.login;
  if (!type || !login) return;
  function sync() {
    const phone = type.value !== "email";
    if (other) other.classList.toggle("hidden", type.value !== "other");
    login.placeholder = phone ? "手机号码，不要再加 0 和区号" : "you@email.com";
    login.setAttribute("inputmode", phone ? "tel" : "email");
  }
  type.addEventListener("change", sync);
  sync();
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
