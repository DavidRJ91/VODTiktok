// ── Configuración fija del repositorio (ya no se pide en el formulario) ──
// Si haces un fork o cambias de repo, edita estas 3 líneas.
const GITHUB_OWNER = "DavidRJ91";
const GITHUB_REPO = "VODTiktok";
const GITHUB_BRANCH = "main";

const WORKFLOW_FILE = "process-tiktok-live.yml";
const $ = (id) => document.getElementById(id);
const els = {
  token: $("token"), saveConnection: $("saveConnection"), connectionState: $("connectionState"),
  connectionCard: $("connectionCard"),
  url: $("tiktokLiveUrl"),
  chunk: $("chunkMinutes"), chunkWrap: $("chunkWrap"),
  title: $("title"), description: $("description"), privacy: $("privacy"),
  scheduledAt: $("scheduledAt"), scheduleWrap: $("scheduleWrap"),
  start: $("start"), status: $("status"), runInfo: $("runInfo"), results: $("results")
};

// Escapa texto antes de insertarlo como HTML. Sin esto, un título de LIVE
// manipulado (título del stream, "Título" del formulario, etc.) podría
// inyectar HTML/JS en la página y robar el token guardado en localStorage.
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function mode() {
  return document.querySelector('input[name="mode"]:checked').value;
}
function connection() {
  return {
    owner: GITHUB_OWNER,
    repo: GITHUB_REPO,
    branch: GITHUB_BRANCH,
    token: els.token.value.trim()
  };
}
function headers(token) {
  return {
    "Accept":"application/vnd.github+json",
    "Authorization":`Bearer ${token}`,
    "X-GitHub-Api-Version":"2022-11-28",
    "Content-Type":"application/json"
  };
}
function setStatus(text, kind="") {
  els.status.textContent = text;
  els.status.className = kind;
}
function updateVisibility() {
  els.chunkWrap.style.display = mode() === "live_chunked" ? "block" : "none";
  els.scheduleWrap.style.display = els.privacy.value === "scheduled" ? "block" : "none";
}
document.querySelectorAll('input[name="mode"]').forEach(x => x.addEventListener("change", updateVisibility));
els.privacy.addEventListener("change", updateVisibility);

// ── Guardado del token + tarjeta de conexión colapsable ──
// El token solo se guarda en localStorage de este navegador; nunca viaja al
// repositorio ni se muestra a otra persona que visite la página.
function refreshConnectionUI() {
  const hasToken = !!els.token.value.trim();
  els.connectionState.textContent = hasToken ? "Acceso configurado ✓" : "Sin configurar";
  els.connectionCard.open = !hasToken; // se abre solo si falta el token
}
els.saveConnection.addEventListener("click", () => {
  localStorage.setItem("tiktok-live-is-token", els.token.value.trim());
  setStatus("Acceso guardado solo en este navegador.", "ok");
  refreshConnectionUI();
});
const savedToken = localStorage.getItem("tiktok-live-is-token");
if (savedToken) els.token.value = savedToken;
refreshConnectionUI();

async function dispatch(c, inputs) {
  const url = `https://api.github.com/repos/${c.owner}/${c.repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  const r = await fetch(url, {method:"POST", headers:headers(c.token), body:JSON.stringify({ref:c.branch, inputs})});
  if (!r.ok) throw new Error(`Error al lanzar el trabajo: ${r.status} ${await r.text()}`);
}

async function findRun(c, startedAt) {
  const url = `https://api.github.com/repos/${c.owner}/${c.repo}/actions/workflows/${WORKFLOW_FILE}/runs?event=workflow_dispatch&per_page=10`;
  const r = await fetch(url, {headers:headers(c.token)});
  if (!r.ok) throw new Error("No se pudieron consultar las ejecuciones.");
  const data = await r.json();
  return data.workflow_runs.find(run => new Date(run.created_at).getTime() >= startedAt - 5000);
}

async function pollRun(c, runId) {
  const url = `https://api.github.com/repos/${c.owner}/${c.repo}/actions/runs/${runId}`;
  while (true) {
    const r = await fetch(url, {headers:headers(c.token)});
    if (!r.ok) throw new Error("No se pudo consultar el estado.");
    const run = await r.json();
    els.runInfo.textContent = `Ejecución #${run.id}: ${run.status}${run.conclusion ? " — "+run.conclusion : ""}`;
    if (run.status === "completed") return run;
    await new Promise(x => setTimeout(x, 5000));
  }
}

async function loadResult(c, runId) {
  const url = `https://raw.githubusercontent.com/${c.owner}/${c.repo}/${c.branch}/run_status/${runId}.json?${Date.now()}`;
  const r = await fetch(url);
  if (!r.ok) {
    els.results.textContent = "El proceso terminó, pero el resultado aún no está disponible.";
    return;
  }
  const data = await r.json();
  const items = data.live_parts?.length ? data.live_parts : (data.main ? [data.main] : []);
  els.results.innerHTML = items.length
    ? items.map(x => `<div class="result"><a target="_blank" rel="noopener" href="${esc(x.video_url)}">${esc(x.title || x.video_url)}</a></div>`).join("")
    : "No se encontraron vídeos.";
}

els.start.addEventListener("click", async () => {
  try {
    const c = connection();
    if (!c.token) throw new Error("Introduce y guarda tu token de acceso primero.");
    const liveUrl = els.url.value.trim();
    if (!liveUrl || !liveUrl.toLowerCase().includes("tiktok.com")) throw new Error("Introduce una URL válida de TikTok.");
    let scheduled = "";
    if (els.privacy.value === "scheduled") {
      if (!els.scheduledAt.value) throw new Error("Selecciona fecha y hora.");
      scheduled = new Date(els.scheduledAt.value).toISOString().replace(/\.\d{3}Z$/, "Z");
      if (new Date(scheduled) <= new Date()) throw new Error("La programación debe ser futura.");
    }
    const inputs = {
      mode: mode(),
      tiktok_live_url: liveUrl,
      chunk_minutes: String(els.chunk.value || 25),
      title: els.title.value.trim(),
      description: els.description.value.trim(),
      privacy: els.privacy.value,
      scheduled_at: scheduled
    };
    els.start.disabled = true;
    const startedAt = Date.now();
    setStatus("Lanzando proceso...");
    await dispatch(c, inputs);
    setStatus("Proceso lanzado. Buscando ejecución...");
    let run;
    for (let i=0;i<12 && !run;i++) {
      await new Promise(x => setTimeout(x, 2000));
      run = await findRun(c, startedAt);
    }
    if (!run) throw new Error("Se aceptó el trabajo, pero no se encontró la ejecución.");
    const finalRun = await pollRun(c, run.id);
    if (finalRun.conclusion === "success") {
      setStatus("Proceso completado.", "ok");
      await new Promise(x => setTimeout(x, 3000));
      await loadResult(c, run.id);
    } else {
      setStatus(`El proceso terminó con: ${finalRun.conclusion}`, "error");
    }
  } catch (e) {
    setStatus(e.message || String(e), "error");
  } finally {
    els.start.disabled = false;
  }
});

updateVisibility();
