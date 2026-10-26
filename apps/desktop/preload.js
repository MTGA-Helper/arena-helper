// Preload bridge — the only surface the renderer gets: one action call.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("arena", {
  action: (name, payload) => ipcRenderer.invoke("arena:action", name, payload),
});
