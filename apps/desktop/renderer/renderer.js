// Arena Helper renderer (Slice 1): engine status, sign-in/register, and a
// signed-in home that proves the engine connection with the live deck list.
// All calls go through the preload bridge; this file holds no URLs and no
// token.

const $ = (id) => document.getElementById(id);

async function refreshEngineStatus() {
  const el = $("engine-status");
  const res = await window.arena.action("engine-health");
  if (res.ok) {
    el.innerHTML = 'Engine: <span class="ok">healthy</span> · database ' +
      res.data.database + " · " + res.data.engines_loaded + " engines loaded";
  } else {
    el.innerHTML = 'Engine: <span class="bad">unreachable</span> — ' + res.error;
  }
}

async function showHome() {
  const session = await window.arena.action("session");
  if (!session.ok || !session.data.signedIn) return;
  $("auth-view").classList.add("hidden");
  $("home-view").classList.remove("hidden");
  $("welcome").textContent = "Signed in as " + session.data.email;
  const res = await window.arena.action("decks");
  if (res.ok) {
    $("decks-summary").textContent =
      "The engine is tracking " + res.data.length + " recommended decks for your collection:";
    $("decks-list").innerHTML = res.data
      .slice(0, 5)
      .map((d) => "<li>" + d.deck_name + " — " + d.completion_percent + "% complete</li>")
      .join("");
  } else {
    $("decks-summary").textContent = "Could not load decks: " + res.error;
  }
}

$("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("auth-error").textContent = "";
  const res = await window.arena.action("login", {
    email: $("email").value.trim(),
    password: $("password").value,
  });
  if (res.ok) showHome();
  else $("auth-error").textContent = res.error;
});

$("register-btn").addEventListener("click", async () => {
  $("auth-error").textContent = "";
  const res = await window.arena.action("register", {
    email: $("email").value.trim(),
    password: $("password").value,
  });
  if (res.ok) {
    $("auth-error").textContent = "Account created — now sign in.";
  } else {
    $("auth-error").textContent = res.error;
  }
});

$("logout-btn").addEventListener("click", async () => {
  await window.arena.action("logout");
  $("home-view").classList.add("hidden");
  $("auth-view").classList.remove("hidden");
});

refreshEngineStatus();
