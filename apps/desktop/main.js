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
const { LogWatcher, defaultLogPath } = require("./watcher");
const { buildPayload } = require("./watcherParse");

const api = new ApiClient();
let accountEmail = null;
let mainWindow = null;

// --- Arena Watcher (Slice 5) ------------------------------------------
// The watcher parses the Player.log whether or not anyone is signed
// in (state is local until synced), but it only ever PUSHES after a
// sign-in gives the API client a token. Syncs are debounced off the
// watcher's change signal and guarded by a payload fingerprint: a
// log that stops changing stops syncing, and a failed sync keeps the
// dirty flag and retries on a timer instead of spinning.
const watcherLogPath = process.env.ARENA_LOG_PATH || defaultLogPath();
let watcher = null;
const watcherSync = {
  dirty: false,
  fingerprint: "",
  lastSyncAt: null,
  lastSummary: null,
  lastError: null,
  timer: null,
  retryTimer: null,
  syncing: false,
};

function startWatcher() {
  if (!watcherLogPath || watcher) return;
  watcher = new LogWatcher({
    logPath: watcherLogPath,
    onChange: () => {
      watcherSync.dirty = true;
      scheduleSync();
    },
  });
  watcher.start();
}

function scheduleSync() {
  if (watcherSync.timer) return;
  watcherSync.timer = setTimeout(() => {
    watcherSync.timer = null;
    void trySync();
  }, 1200);
}

async function trySync() {
  if (!watcher || watcherSync.syncing) return;
  if (!api.token || !watcherSync.dirty) return;
  const payload = buildPayload(watcher.getState());
  if (payload.decks.length === 0 && !payload.inventory) {
    watcherSync.dirty = false;
    return;
  }
  // Fingerprint = size + djb2 over the serialized payload; enough to
  // detect "the same state again" without storing a second copy.
  const serialized = JSON.stringify(payload);
  let hash = 5381;
  for (let i = 0; i < serialized.length; i++) {
    hash = ((hash << 5) + hash + serialized.charCodeAt(i)) | 0;
  }
  const fingerprint = serialized.length + ":" + hash;
  if (fingerprint === watcherSync.fingerprint) {
    watcherSync.dirty = false;
    return;
  }
  watcherSync.syncing = true;
  try {
    const summary = await api.syncWatcher(payload);
    watcherSync.fingerprint = fingerprint;
    watcherSync.dirty = false;
    watcherSync.lastSyncAt = new Date().toISOString();
    watcherSync.lastSummary = summary;
    watcherSync.lastError = null;
  } catch (e) {
    watcherSync.lastError = String((e && e.message) || e);
    if (!watcherSync.retryTimer) {
      watcherSync.retryTimer = setTimeout(() => {
        watcherSync.retryTimer = null;
        scheduleSync();
      }, 30000);
    }
  } finally {
    watcherSync.syncing = false;
  }
}

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
        // Slice 5: a sign-in is a sync trigger — whatever the watcher
        // already parsed lands now, not at the next log change.
        watcherSync.dirty = true;
        scheduleSync();
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
      case "watcher-status":
        return { ok: true, data: {
          available: watcher !== null,
          signedIn: Boolean(api.token),
          watcher: watcher ? watcher.getStatus() : null,
          sync: {
            dirty: watcherSync.dirty,
            lastSyncAt: watcherSync.lastSyncAt,
            lastSummary: watcherSync.lastSummary,
            lastError: watcherSync.lastError,
          },
        } };
      default:
        return { ok: false, error: "Unknown action: " + action };
    }
  } catch (e) {
    return { ok: false, error: e.message, status: e.status || null };
  }
});

app.whenReady().then(() => {
  startWatcher();
  createWindow();
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on("before-quit", () => {
  if (watcher) watcher.stop();
});
