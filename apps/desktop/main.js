// Arena Helper desktop shell — main process (Slice 1, Oct 26, 2026).
//
// Thin native shell around the live engine API: window management plus a
// single IPC entry point. The renderer names an action, never a URL, and
// never receives the session token (see api.js).

const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { ApiClient } = require("./api");

const api = new ApiClient();
let accountEmail = null;

function createWindow() {
  const win = new BrowserWindow({
    width: 1024,
    height: 720,
    title: "Arena Helper",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

ipcMain.handle("arena:action", async (_evt, action, payload = {}) => {
  try {
    switch (action) {
      case "engine-health":
        return { ok: true, data: await api.health() };
      case "decks":
        return { ok: true, data: await api.decks() };
      case "register":
        return { ok: true, data: await api.register(payload.email, payload.password) };
      case "login": {
        const data = await api.login(payload.email, payload.password);
        accountEmail = payload.email;
        // Token stays in the main process; the renderer gets identity only.
        return { ok: true, data: { email: accountEmail, tokenType: data.token_type || "bearer" } };
      }
      case "logout":
        api.logout();
        accountEmail = null;
        return { ok: true, data: null };
      case "session":
        return { ok: true, data: { signedIn: Boolean(api.token), email: accountEmail, apiBase: api.base } };
      default:
        return { ok: false, error: "Unknown action: " + action };
    }
  } catch (e) {
    return { ok: false, error: e.message, status: e.status || null };
  }
});

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
