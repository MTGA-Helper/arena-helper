// Arena Helper desktop — engine API client (main process only).
//
// Slice 1 (TURBO surge, Oct 26, 2026): the renderer never talks to the
// engine directly and never sees the session token. All requests go
// through this client in the main process; the token is held in memory
// for the session only — nothing is written to disk in Slice 1.
//
// Slice 2 (TURBO surge, Oct 26, 2026): collection read + CSV upload.
// The upload is multipart form data, so it cannot ride the JSON request
// helper; uploadCollectionCsv posts FormData through the same
// error-handling path so failures read the same way everywhere.
//
// Slice 3 (TURBO surge, Oct 26, 2026): deck detail — one deck's
// full card list + its stored engine analysis.
//
// Slice 4 (TURBO surge, Oct 26, 2026): next-action — the engine's
// computed recommendation for the signed-in collection.
//
// Base URL override: ARENA_API_BASE (used by the smoke test to point at
// a locally booted API). Default is the production engine.

const DEFAULT_BASE = "https://arena-helper.onrender.com";

class ApiClient {
  constructor(base = process.env.ARENA_API_BASE || DEFAULT_BASE) {
    this.base = String(base).replace(/\/+$/, "");
    this.token = null;
  }

  // Shared response handling: parse the body, and on failure throw an
  // Error whose message is the engine's own detail, read plainly.
  async _send(respPromise) {
    let resp;
    try {
      resp = await respPromise;
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

  async request(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = "Bearer " + this.token;
    return this._send(fetch(this.base + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    }));
  }

  health() { return this.request("GET", "/api/health"); }
  decks() { return this.request("GET", "/recommendations/decks"); }
  deckDetail(deckId) { return this.request("GET", "/recommendations/decks/" + deckId); }
  nextAction() { return this.request("GET", "/recommendations/next-action"); }
  register(email, pw) { return this.request("POST", "/auth/register", { email, password: pw }); }

  async login(email, pw) {
    const data = await this.request("POST", "/auth/login", { email, password: pw });
    if (data && data.access_token) this.token = data.access_token;
    return data;
  }

  logout() { this.token = null; }

  // --- Slice 2: collection -------------------------------------------
  // The engine resolves "the current user" server-side for these routes;
  // the token rides along when present, exactly like every other call.

  collection() { return this.request("GET", "/collection"); }
  collectionStats() { return this.request("GET", "/collection/stats"); }

  // POST /collection/upload replaces the engine-side collection with the
  // CSV's contents (the endpoint's documented source-of-truth semantics)
  // and returns the import summary. csvText is the file's full text; the
  // filename matters only for the endpoint's .csv extension check.
  uploadCollectionCsv(csvText, filename = "collection.csv") {
    const form = new FormData();
    form.append("file", new Blob([csvText], { type: "text/csv" }), filename);
    const headers = {};
    if (this.token) headers["Authorization"] = "Bearer " + this.token;
    return this._send(fetch(this.base + "/collection/upload", {
      method: "POST",
      headers,
      body: form,
    }));
  }
}

module.exports = { ApiClient, DEFAULT_BASE };
