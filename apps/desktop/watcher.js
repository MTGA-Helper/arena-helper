"use strict";

// Arena Watcher tail engine (Slice 5, Oct 26, 2026). watcherParse.js
// decides what a line MEANS; this module owns the unglamorous half:
// following a log file that Arena holds open and appends to live,
// without ever loading it whole.
//
// Robustness contract (the acceptance criteria, as code):
//   - Incremental reads only: a byte offset is kept and each poll
//     reads just the bytes appended since the last one. Memory is
//     bounded by the parser's state (latest decks + inventory) plus
//     one partial-line buffer — a 5 MB log and a 500 MB log cost
//     the same working set.
//   - Partial lines are never parsed: only newline-terminated text
//     is fed on. Arena can be mid-write at any poll; the remainder
//     waits in the buffer for its newline. A single line is capped
//     (the real session dump is ~0.5 MB): past MAX_LINE_BYTES with
//     no newline, the buffer is dropped and counted rather than
//     grown forever.
//   - Rotation / truncation: when the file shrinks below the read
//     offset (Arena restarts and truncates Player.log, or a new
//     session replaces it), the offset and buffer reset AND the
//     parse state resets with them — the new file is a new session
//     dump, and state from the dead session must not linger in the
//     next sync. onChange fires so the fresh state syncs.
//   - A missing file is a normal state (game not installed / not run
//     yet), reported via getStatus().found, never an exception.
//   - Polling, not fs.watch: one stat per interval is cheap, behaves
//     identically on macOS and Windows, and cannot miss events the
//     way platform watchers do across rotation. 1.5 s is well inside
//     "the deck you just saved appears" patience.
//
// require()d by the Electron main process and by the smoke suite
// (plain node), same as the other shared desktop modules.

const fs = require("fs");
const os = require("os");
const path = require("path");
const { createState, feedLine } = require("./watcherParse");

const MAX_LINE_BYTES = 16 * 1024 * 1024;
const DEFAULT_POLL_MS = 1500;

// Where MTG Arena writes Player.log, per platform — the paths the
// client actually uses (verified on this Mac for darwin; the win32
// LocalLow path is the client's documented location and is a
// standing Slice 6 verification item, like the rest of the Windows
// lane). ARENA_LOG_PATH overrides in main.js for tests and support.
function defaultLogPath(platform = process.platform, home = os.homedir()) {
  if (platform === "win32") {
    return path.join(
      home, "AppData", "LocalLow", "Wizards Of The Coast", "MTGA", "Player.log",
    );
  }
  if (platform === "darwin") {
    return path.join(
      home, "Library", "Logs", "Wizards Of The Coast", "MTGA", "Player.log",
    );
  }
  // Linux: Arena runs through Steam/Proton with per-install compat
  // paths; there is no single canonical location to point at, so the
  // watcher reports no path rather than guessing one.
  return null;
}

class LogWatcher {
  constructor(options) {
    this.logPath = options.logPath;
    this.onChange = typeof options.onChange === "function" ? options.onChange : () => {};
    this.pollMs = options.pollMs || DEFAULT_POLL_MS;
    this.state = createState();
    this.offset = 0;
    this.buffer = "";
    this.found = false;
    this.rotations = 0;
    this.droppedOversizeLines = 0;
    this.timer = null;
    this.reading = false;
    this.lastError = null;
  }

  start() {
    if (this.timer) return;
    this._poll();
    this.timer = setInterval(() => this._poll(), this.pollMs);
    if (typeof this.timer.unref === "function") this.timer.unref();
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  getState() {
    return this.state;
  }

  getStatus() {
    return {
      logPath: this.logPath,
      found: this.found,
      offset: this.offset,
      rotations: this.rotations,
      droppedOversizeLines: this.droppedOversizeLines,
      lastError: this.lastError,
      stats: { ...this.state.stats },
      deckCount: Object.keys(this.state.decks).length,
      inventorySeen: this.state.inventory !== null,
    };
  }

  _resetForRotation() {
    this.offset = 0;
    this.buffer = "";
    this.state = createState();
    this.rotations += 1;
    this.onChange();
  }

  _poll() {
    if (this.reading || !this.logPath) return;
    fs.stat(this.logPath, (err, st) => {
      if (err) {
        // Not existing yet is the expected pre-game state.
        this.found = false;
        return;
      }
      this.found = true;
      if (st.size < this.offset) {
        this._resetForRotation();
      }
      if (st.size === this.offset || this.reading) return;
      this.reading = true;
      const start = this.offset;
      const stream = fs.createReadStream(this.logPath, {
        start,
        end: st.size - 1,
        encoding: "utf8",
      });
      let advanced = 0;
      stream.on("data", (chunk) => {
        advanced += Buffer.byteLength(chunk, "utf8");
        this._consume(chunk);
      });
      stream.on("error", (e) => {
        this.lastError = String((e && e.message) || e);
        this.reading = false;
      });
      stream.on("end", () => {
        // Advance only by bytes actually consumed: a write racing
        // the read is picked up by the next poll, never skipped.
        this.offset = start + advanced;
        this.reading = false;
      });
    });
  }

  _consume(chunk) {
    this.buffer += chunk;
    let changed = false;
    let idx = this.buffer.indexOf("\n");
    while (idx >= 0) {
      const line = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 1);
      if (feedLine(this.state, line.endsWith("\r") ? line.slice(0, -1) : line)) {
        changed = true;
      }
      idx = this.buffer.indexOf("\n");
    }
    if (this.buffer.length > MAX_LINE_BYTES) {
      this.buffer = "";
      this.droppedOversizeLines += 1;
    }
    if (changed) this.onChange();
  }
}

module.exports = { LogWatcher, defaultLogPath, MAX_LINE_BYTES };
