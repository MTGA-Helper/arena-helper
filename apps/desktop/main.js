// Arena Helper desktop shell — main process (Slice 1, Oct 26, 2026).
//
// Thin native shell around the live engine API: window management plus a
// single IPC entry point. The renderer names an action, never a URL, and
// never receives the session token (see api.js).
//
// Slice 3 (Oct 26, 2026): "deck-detail" fetches one deck's full
// card list + stored analysis for the decks view.
//
// Slice 4 (Oct 26, 2026): "next-action" fetches the engine's
// recommendation for the Recommendations section.
//
// Slice 2 (Oct 26, 2026): collection actions. "collection" returns the
// list + stats in one round trip. "collection-upload" opens the CSV file
// picker HERE in the main process — the renderer never touches the
// filesystem or a file path — reads the file, uploads it through the API
// client, and returns the import summary with the refreshed list + stats
// so the UI can show the reconciled counts immediately.

const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const fs = require("fs");
const path = require("path");
const { ApiClient } = require("./api");

const api = new ApiClient();
let accountEmail = null;
let mainWindow = null;

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
  mainWindow = win;
  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

async function collectionSnapshot() {
  const [list, stats] = await Promise.all([api.collection(), api.collectionStats()]);
  return { list, stats };
}

ipcMain.handle("arena:action", async (_evt, action, payload = {}) => {
  try {
    switch (action) {
      case "engine-health":
        return { ok: true, data: await api.health() };
      case "decks":
        return { ok: true, data: await api.decks() };
      case "deck-detail":
        return { ok: true, data: await api.deckDetail(payload.deckId) };
      case "next-action":
        return { ok: true, data: await api.nextAction() };
      case "register":
        return { ok: true, data: await api.register(payload.email, payload.pw) };
      case "login": {
        const data = await api.login(payload.email, payload.pw);
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
      case "collection":
        return { ok: true, data: await collectionSnapshot() };
      case "collection-upload": {
        const picked = await dialog.showOpenDialog(mainWindow, {
          title: "Choose a collection CSV",
          properties: ["openFile"],
          filters: [{ name: "CSV files", extensions: ["csv"] }],
        });
        if (picked.canceled || picked.filePaths.length === 0) {
          return { ok: true, data: { canceled: true } };
        }
        const filePath = picked.filePaths[0];
        const csvText = await fs.promises.readFile(filePath, "utf8");
        const summary = await api.uploadCollectionCsv(csvText, path.basename(filePath));
        const snapshot = await collectionSnapshot();
        return { ok: true, data: { canceled: false, summary, ...snapshot } };
      }
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
