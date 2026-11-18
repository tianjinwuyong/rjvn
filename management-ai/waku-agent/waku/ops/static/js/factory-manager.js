// Factory manager visual monitor. Read-only MES observation plus an explicit
// pause/resume control for the monitor itself.
let factoryManagerState = null;
let factoryManagerBusy = false;

function fmAge(iso){
  if (!iso) return "not run yet";
  const t = Date.parse(iso); if (!Number.isFinite(t)) return iso;
  const sec = Math.max(0, Math.round((Date.now()-t)/1000));
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.round(sec/60)}m ago`;
  return `${Math.round(sec/3600)}h ago`;
}
function fmPriority(p){
  const cls = p === "high" ? "fm-high" : p === "medium" ? "fm-medium" : "fm-low";
  return `<span class="fm-priority ${cls}">${esc(p || "normal")}</span>`;
}
function fmStatus(s){
  const running = !!s && s.running !== false;
  return `<span class="fm-live ${running ? "on" : "off"}"><span class="fm-live-dot"></span>${running ? "monitoring" : "paused"}</span>`;
}
function fmTaskCard(t){
  const title = t.title || t.type || "Manager task";
  return `<article class="fm-task">
    <div class="fm-task-top"><span class="fm-task-type">${esc(t.type || "TASK")}</span>${fmPriority(t.priority)}<span class="fm-task-status">${esc(t.status || "open")}</span></div>
    <h3>${esc(title)}</h3>
    <p>${esc(t.detail || "No additional detail")}</p>
    <div class="fm-task-meta"><span>source <b>${esc(t.source || "—")}</b></span><span>owner <b>${esc(t.owner || "manager")}</b></span><span>${esc(fmAge(t.createdAt))}</span></div>
  </article>`;
}
function fmWorkflow(){
  return `<div class="fm-flow" aria-label="Factory manager work cycle">
    <div class="fm-flow-step done"><span>1</span><b>Read</b><small>MES · WMS</small></div><i></i>
    <div class="fm-flow-step active"><span>2</span><b>Observe</b><small>lines &amp; events</small></div><i></i>
    <div class="fm-flow-step"><span>3</span><b>Decide</b><small>risk &amp; priority</small></div><i></i>
    <div class="fm-flow-step"><span>4</span><b>Assign</b><small>owner queue</small></div>
  </div>`;
}
async function loadFactoryManager(){
  try { factoryManagerState = await (await fetch("/api/factory-manager/tasks", {cache:"no-store"})).json(); }
  catch(e){ factoryManagerState = {error:String(e),tasks:[]}; }
  if (activeView === "factory-manager") renderFactoryManagerInto();
}
function renderFactoryManagerInto(){
  const root = document.getElementById("factory-manager-root"); if (!root) return;
  const s = factoryManagerState || {tasks:[]};
  const tasks = (s.tasks || []).filter(t => t.status !== "closed");
  const high = tasks.filter(t => t.priority === "high").length;
  const last = s.lastRun ? fmAge(s.lastRun) : "not run yet";
  const isRunning = s.running !== false;
  root.innerHTML = `<div class="fm-toolbar"><div><div class="fm-kicker">FACTORY CONTROL ROOM</div><div class="fm-statusline">${fmStatus(s)} <span>last check ${esc(last)}</span><span>every ${esc(String(s.intervalSeconds || 300))}s</span></div></div>
    <div class="fm-actions"><button class="save" onclick="factoryManagerRun()" ${factoryManagerBusy?"disabled":""}>${factoryManagerBusy?"Checking…":"Run check now"}</button><button class="save ghost" onclick="factoryManagerToggle()">${isRunning?"Pause monitor":"Resume monitor"}</button></div></div>
    ${s.error || s.lastError ? `<div class="fm-alert">${esc(s.error || s.lastError)}</div>` : ""}
    <div class="fm-hero"><div><h2>What the manager is doing now</h2><p>Watching MES and WMS, finding exceptions, and placing human-owned work in the queue. It does not change production records.</p></div><div class="fm-radar"><span></span><b>${isRunning?"LIVE":"PAUSED"}</b></div></div>
    ${fmWorkflow()}
    <div class="fm-metrics"><div><b>${tasks.length}</b><span>open tasks</span></div><div><b class="${high?"fm-number-bad":""}">${high}</b><span>high priority</span></div><div><b>${esc(String(s.intervalSeconds || 300))}s</b><span>check interval</span></div></div>
    <div class="fm-section-head"><h2>Manager task queue</h2><span>${tasks.length?"needs attention":"all clear"}</span></div>
    <div class="fm-tasks">${tasks.length ? tasks.map(fmTaskCard).join("") : `<div class="fm-empty"><div class="fm-empty-icon">✓</div><b>No open tasks</b><span>The latest observation found nothing requiring attention.</span></div>`}</div>`;
}
async function factoryManagerRun(){
  if (factoryManagerBusy) return; factoryManagerBusy = true; renderFactoryManagerInto();
  try { factoryManagerState = await (await fetch("/api/factory-manager/run", {method:"POST"})).json(); }
  catch(e){ factoryManagerState = {error:String(e),tasks:[]}; }
  factoryManagerBusy = false; renderFactoryManagerInto();
}
async function factoryManagerToggle(){
  const running = factoryManagerState && factoryManagerState.running !== false;
  try { factoryManagerState = await (await fetch(`/api/factory-manager/${running?"stop":"start"}`, {method:"POST"})).json(); }
  catch(e){ factoryManagerState = {error:String(e),tasks:[]}; }
  renderFactoryManagerInto();
}
function factoryManagerView(){
  setTimeout(loadFactoryManager, 0);
  return `<div id="factory-manager-root"><div class="fm-loading"><span class="fm-spinner"></span> Connecting to the manager monitor…</div></div>`;
}
// Loaded after views.js so the view registry is already available.
VIEWS["factory-manager"] = factoryManagerView;
