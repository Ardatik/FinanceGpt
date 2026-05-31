export const API_BASE = import.meta.env.VITE_API_URL || "/api";
const ACCESS_TOKEN_KEY = "financepay_access_token";
const REFRESH_TOKEN_KEY = "financepay_refresh_token";
const USER_KEY = "financepay_user";
const LEGACY_TOKEN_KEY = "financepay_token";

function absoluteUrl(base) {
  if (base.startsWith("http://") || base.startsWith("https://")) {
    return base;
  }
  return `${window.location.origin}${base.startsWith("/") ? base : `/${base}`}`;
}

export const API_ABSOLUTE_BASE = absoluteUrl(API_BASE);
export const WS_BASE = API_ABSOLUTE_BASE.replace(/^http/, "ws");
let refreshPromise = null;

export function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Number(value)) + " ₽";
}

export function isMobileDevice() {
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) || (window.matchMedia?.("(pointer: coarse)").matches && window.innerWidth < 900);
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY) || "";
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY) || "";
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function saveAuthSession(session) {
  localStorage.setItem(ACCESS_TOKEN_KEY, session.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, session.refresh_token);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  if (session.user) {
    localStorage.setItem(USER_KEY, JSON.stringify(session.user));
  }
  window.dispatchEvent(new CustomEvent("financepay:auth-updated", { detail: session }));
}

export function clearAuthSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new CustomEvent("financepay:auth-updated", { detail: null }));
}

async function parseResponse(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text;
  }
}

async function refreshSession() {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) throw new Error("Refresh token отсутствует");
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    const data = await parseResponse(response);
    if (!response.ok) {
      clearAuthSession();
      throw new Error(data?.detail || data?.message || "Сессия истекла");
    }
    saveAuthSession(data);
    return data;
  })().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function rawRequest(path, { method, body, headers }, bearerToken) {
  return fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(bearerToken ? { Authorization: `Bearer ${bearerToken}` } : {}),
      ...headers
    },
    body: body ? JSON.stringify(body) : undefined
  });
}

export async function apiRequest(path, { method = "GET", token, body, headers = {}, skipRefresh = false } = {}) {
  let bearerToken = token || "";
  let response = await rawRequest(path, { method, body, headers }, bearerToken);
  let data = await parseResponse(response);
  if (response.status === 401 && bearerToken && !skipRefresh && getRefreshToken()) {
    const session = await refreshSession();
    bearerToken = session.access_token;
    response = await rawRequest(path, { method, body, headers }, bearerToken);
    data = await parseResponse(response);
  }
  if (!response.ok) {
    throw new Error(data?.detail || data?.message || "Ошибка запроса");
  }
  return data;
}
