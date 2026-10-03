const $ = (id) => document.getElementById(id);

function formatAge(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour12: false });
  } catch {
    return "--:--:--";
  }
}

function ageFromBirth(birth) {
  if (!birth) return null;
  const t = Date.parse(birth);
  if (Number.isNaN(t)) return null;
  return Math.floor((Date.now() - t) / 1000);
}

let lastPhase = "";

function render(state) {
  $("name").textContent = state.identity.name || "Entity";
  $("selfDescription").textContent = state.identity.self_description || "Still forming.";
  $("tickCount").textContent = String(state.identity.tick_count ?? 0);
  $("age").textContent = formatAge(ageFromBirth(state.identity.birth));
  $("entityId").textContent = state.identity.entity_id || "";

  const phase = state.state.phase || "REST";
  const phaseEl = $("phase");
  if (phase !== lastPhase) {
    phaseEl.classList.remove("pulse");
    void phaseEl.offsetWidth;
    phaseEl.classList.add("pulse");
    lastPhase = phase;
  }
  phaseEl.textContent = phase;

  $("quietFlag").classList.toggle("hidden", !state.state.quiet_mode);
  $("pausedFlag").classList.toggle("hidden", !state.state.paused);

  $("brainRev").textContent = String(state.brain.revision ?? 0);
  $("brainChange").textContent = state.brain.latest_change || "—";
  $("brainHash").textContent = state.brain.content_hash || "—";

  $("inference").textContent = state.quota.inference || "—";
  $("requestsToday").textContent = String(state.quota.requests_today ?? 0);

  const help = state.help_board;
  $("helpBoard").textContent =
    help.message ||
    (help.requests && help.requests.length
      ? `${help.requests.length} open`
      : "NO HELP REQUESTS");

  const drives = $("drives");
  drives.innerHTML = "";
  (state.drives || []).forEach((d) => {
    const li = document.createElement("li");
    li.textContent = d;
    drives.appendChild(li);
  });

  const traits = $("traits");
  traits.innerHTML = "";
  const list = state.personality?.traits || [];
  if (!list.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "None discovered yet";
    empty.style.textTransform = "none";
    empty.style.fontFamily = "var(--font-serif)";
    traits.appendChild(empty);
  } else {
    list.forEach((t) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = t.trait;
      const conf = document.createElement("span");
      conf.className = "conf";
      conf.textContent = Number(t.confidence).toFixed(2);
      li.append(name, conf);
      traits.appendChild(li);
    });
  }

  const stream = $("thoughtStream");
  stream.innerHTML = "";
  const thoughts = state.thought_stream || [];
  if (!thoughts.length) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = "Waiting for the first tick…";
    stream.appendChild(p);
  } else {
    thoughts.slice(-18).forEach((item, idx) => {
      const row = document.createElement("div");
      row.className = "thought";
      row.style.animationDelay = `${idx * 20}ms`;
      const time = document.createElement("time");
      time.textContent = formatTime(item.timestamp);
      const text = document.createElement("p");
      text.textContent = item.narration;
      row.append(time, text);
      stream.appendChild(row);
    });
  }
}

async function poll() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const state = await res.json();
    render(state);
  } catch (err) {
    console.error(err);
  }
}

poll();
setInterval(poll, 1000);
