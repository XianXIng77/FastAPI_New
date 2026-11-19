const registerForm = document.getElementById("register");
const loginForm = document.getElementById("login");
const state = document.getElementById("state");
const statusLine = document.getElementById("status");
const output = document.getElementById("output");
const protectedButtons = ["profile", "refresh", "logout"];
const sensitiveFields = new Set(["access_token", "refresh_token", "password", "hashed_password"]);
let tokens = null;
let revokedTokens = null;
let busy = false;

function renderControls() {
  for (const button of document.querySelectorAll("button")) {
    button.disabled = busy ||
      (protectedButtons.includes(button.id) && !tokens) ||
      (button.id === "verify-logout" && !revokedTokens);
  }
  state.textContent = tokens ? "页面已持有令牌" : "页面未持有令牌";
}

async function request(endpoint, { method = "POST", payload, accessToken } = {}) {
  const headers = { Accept: "application/json" };
  if (payload !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = "Bearer " + accessToken;
  const response = await fetch("../auth/" + endpoint, {
    method, headers, body: payload === undefined ? undefined : JSON.stringify(payload),
    cache: "no-store", credentials: "omit", redirect: "error"
  });
  const body = response.headers.get("content-type")?.includes("application/json")
    ? await response.json()
    : null;
  return { endpoint: method + " /auth/" + endpoint, status: response.status, ok: response.ok, body };
}

async function run(label, action) {
  if (busy) return;
  busy = true;
  renderControls();
  statusLine.dataset.state = "";
  statusLine.textContent = label + "：请求中…";
  output.textContent = "";
  try {
    const response = await action();
    statusLine.dataset.state = response.ok ? "ok" : "error";
    statusLine.textContent = response.endpoint + " · " + response.status;
    output.textContent = response.body === null && response.status >= 500
      ? "服务端错误。请检查 FastAPI 日志和数据库迁移是否已执行。"
      : JSON.stringify(response.body, (key, value) =>
        sensitiveFields.has(key) ? "（已隐藏）" : value, 2);
  } catch {
    statusLine.dataset.state = "error";
    statusLine.textContent = label + "：未能读取响应";
    output.textContent = "请确认 FastAPI 正在运行。如果刷新未收到响应，请重新登录，不要重试旧刷新令牌。";
  } finally {
    busy = false;
    renderControls();
  }
}

registerForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(registerForm));
  run("注册", async () => {
    const response = await request("register", { payload });
    if (response.ok) {
      loginForm.elements.email.value = payload.email;
      registerForm.elements.password.value = "";
    }
    return response;
  });
});

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(loginForm));
  run("登录", async () => {
    const response = await request("login", { payload });
    if (response.ok) {
      tokens = response.body.data;
      revokedTokens = null;
      loginForm.elements.password.value = "";
    }
    return response;
  });
});

document.getElementById("profile").addEventListener("click", () => {
  run("查询用户", () => request("me", { method: "GET", accessToken: tokens.access_token }));
});

document.getElementById("anonymous").addEventListener("click", () => {
  run("未登录请求", () => request("me", { method: "GET" }));
});

document.getElementById("refresh").addEventListener("click", () => {
  run("刷新", async () => {
    try {
      const response = await request("refresh", { payload: { refresh_token: tokens.refresh_token } });
      if (response.ok) tokens = response.body.data;
      if (response.status === 401) tokens = null;
      return response;
    } catch (error) {
      tokens = null;
      throw error;
    }
  });
});

document.getElementById("logout").addEventListener("click", () => {
  run("退出", async () => {
    const response = await request("logout", { accessToken: tokens.access_token });
    if (response.ok) {
      revokedTokens = tokens;
      tokens = null;
    }
    return response;
  });
});

document.getElementById("verify-logout").addEventListener("click", () => {
  run("验证退出", async () => {
    const access = await request("me", { method: "GET", accessToken: revokedTokens.access_token });
    const refresh = await request("refresh", { payload: { refresh_token: revokedTokens.refresh_token } });
    const ok = access.status === 401 && refresh.status === 401;
    revokedTokens = null;
    return { ok, endpoint: "验证退出失效", status: ok ? "通过" : "未通过", body: [access, refresh] };
  });
});

renderControls();
