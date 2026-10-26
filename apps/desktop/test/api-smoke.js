// Slice 1 smoke test for the desktop API client (plain Node, no Electron).
//
//   node test/api-smoke.js
//
// Uses ARENA_API_BASE (default: production engine). Two modes:
//  - read-only checks (health + decks) always run;
//  - the auth round-trip runs only when ARENA_SMOKE_AUTH=1, and must only be
//    pointed at a LOCAL api instance — it creates a throwaway account.
//    Never run the auth leg against production.

const { ApiClient } = require("../api");

const RUN_AUTH = process.env.ARENA_SMOKE_AUTH === "1";
let failures = 0;

function check(name, cond, detail = "") {
  console.log((cond ? "PASS" : "FAIL") + " - " + name + (detail ? " " + detail : ""));
  if (!cond) failures++;
}

// Each leg is isolated: a thrown error fails that leg, never aborts the run.
async function leg(name, fn) {
  try {
    await fn();
  } catch (e) {
    check(name, false, "(" + e.message + ")");
  }
}

(async () => {
  const api = new ApiClient();
  console.log("API base:", api.base);

  await leg("health ok", async () => {
    const health = await api.health();
    check("health ok", health && health.status === "healthy", JSON.stringify(health));
  });

  if (process.env.ARENA_SMOKE_DECKS === "0") {
    console.log("SKIP - decks (ARENA_SMOKE_DECKS=0; local fixture has no card corpus)");
  } else {
    await leg("decks returns a list", async () => {
      const decks = await api.decks();
      check("decks returns a list", Array.isArray(decks), "count=" + (decks && decks.length));
    });
  }

  await leg("bad login is rejected", async () => {
    try {
      await api.login("nobody@example.com", "wrong-password");
      check("bad login is rejected", false, "login unexpectedly succeeded");
    } catch (e) {
      check("bad login is rejected", e.status === 401, "(" + e.message + ")");
    }
  });

  if (RUN_AUTH) {
    await leg("auth round-trip", async () => {
      // Fixture addresses use example.com: the API's EmailStr validation
      // rejects special-use TLDs such as .invalid with a 422.
      const email = "slice1-smoke+" + Date.now() + "@example.com";
      // Throwaway smoke credential for the local instance only; never a real account.
      const password = "smoke-" + Date.now();
      const reg = await api.register(email, password);
      // The register endpoint answers 201 {"message": "User created
      // successfully"} — a resolved promise here already means success.
      check("register accepted (201)", Boolean(reg && (reg.message || reg.email || reg.id)),
        JSON.stringify(reg).slice(0, 120));
      const login = await api.login(email, password);
      check("login returns a token", Boolean(login && login.access_token));
      check("client holds the token after login", Boolean(api.token));
      api.logout();
      check("logout clears the token", api.token === null);
    });
  } else {
    console.log("SKIP - auth round-trip (set ARENA_SMOKE_AUTH=1 against a LOCAL api)");
  }

  console.log("RESULT:", failures === 0 ? "ALL PASS" : failures + " FAILURES");
  process.exit(failures === 0 ? 0 : 1);
})().catch((e) => {
  console.error("SMOKE ERROR:", e.message);
  process.exit(1);
});
