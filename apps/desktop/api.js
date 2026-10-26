// Arena Helper desktop — engine API client (main process only).
//
// Slice 1 (TURBO surge, Oct 26, 2026): the renderer never talks to the
// engine directly and never sees the session token. All requests go
// through this client in the main process; the token is held in memory
// for the session only — nothing is written to disk in Slice 1.
//
// Base URL override: ARENA_API_BASE (used by the smoke test to point at
// a locally booted API). Default is the production engine.

const DEFAULT_BASE = "https://arena-helper.onrender.com";

class ApiClient {
  constructor(base = process.env.ARENA_API_BASE || DEFAULT_BASE) {
    this.base = String(base).replace(/\/+$/, "");
    this.token = null;
  }

  async request(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = "Bearer " + this.token;
    let resp;
    try {
      resp = await fetch(this.base + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (e) {
      // Network-level failure (DNS, refused, offline): say so plainly.
      throw new Error("Engine unreachable at " + this.base + " (" + e.message + ")");
    }
    const text = await resp.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch { data = { raw: text }; }
    }
    if (!resp.ok) {
      // FastAPI error detail is a string for HTTP errors but an ARRAY of
      // {msg, ...} objects for 422 validation errors — render both plainly
      // (the array form used to surface as "[object Object]").
      const raw = data && data.detail;
      const detail = Array.isArray(raw)
        ? raw.map((d) => (d && d.msg) || JSON.stringify(d)).join("; ")
        : raw || resp.statusText || "request failed";
      const err = new Error("HTTP " + resp.status + ": " + detail);
      err.status = resp.status;
      throw err;
    }
    return data;
  }

  health() { return this.request("GET", "/api/health"); }
  decks() { return this.request("GET", "/recommendations/decks"); }
  register(email, password) { return this.request("POST", "/auth/register", { email, password }); }

  async login(email, password) {
    const data = await this.request("POST", "/auth/login", { email, password });
    if (data && data.access_token) this.token = data.access_token;
    return data;
  }

  logout() { this.token = null; }
}

module.exports = { ApiClient, DEFAULT_BASE };
