let stationToolboxTimer = null;

async function renderStationToolbox() {
  const content = document.getElementById('pageContent');
  content.innerHTML = `
    <div class="page-header">
      <div class="page-header-left">
        <div class="page-title">Station Agent Toolbox</div>
        <div class="page-subtitle">Read-only MES and station connectivity monitor</div>
      </div>
      <div class="btn-group"><button class="btn btn-primary" onclick="refreshStationToolbox()">🔄 Refresh</button></div>
    </div>
    <div id="stationToolboxSummary" class="grid grid-3" style="margin-bottom:20px">${renderSkeleton(3)}</div>
    <div class="section-title">Manual stations</div>
    <div class="card" style="padding:0;overflow:auto"><table class="data-table"><thead><tr><th>Station</th><th>WinRM</th><th>SSH</th><th>Scanner 1003</th><th>Overall</th></tr></thead><tbody id="stationToolboxRows"><tr><td colspan="5"><div class="loading"><div class="loading-spinner"></div>Checking stations…</div></td></tr></tbody></table></div>
    <div class="text-sm text-muted" style="margin-top:14px">This first version is read-only. Remote start/stop actions will be allowlisted and audited before being enabled.</div>
  `;
  await refreshStationToolbox();
  if (stationToolboxTimer) clearInterval(stationToolboxTimer);
  stationToolboxTimer = setInterval(refreshStationToolbox, 30000);
}

async function refreshStationToolbox() {
  try {
    const data = await api.getStationToolboxStatus();
    const mes = data.mes || {};
    const stations = data.stations || [];
    const online = stations.filter(s => s.reachable).length;
    document.getElementById('stationToolboxSummary').innerHTML = `
      <div class="card"><div class="card-title">MES</div><div class="stat-value" style="color:var(--${mes.reachable ? 'green' : 'red'})">${mes.reachable ? 'ONLINE' : 'OFFLINE'}</div><div class="text-sm text-muted">${mes.latency_ms ?? '—'} ms · ${escapeHtml(mes.url || '')}</div></div>
      <div class="card"><div class="card-title">Stations</div><div class="stat-value">${online}/${stations.length}</div><div class="text-sm text-muted">At least one agent port reachable</div></div>
      <div class="card"><div class="card-title">Last update</div><div class="stat-value" style="font-size:18px">${new Date(data.updated).toLocaleTimeString()}</div><div class="text-sm text-muted">WinRM · SSH · scanner 1003</div></div>`;
    document.getElementById('stationToolboxRows').innerHTML = stations.map(s => {
      const p = s.ports || {};
      return `<tr><td><strong>${escapeHtml(s.name)}</strong><div class="text-sm text-muted">${escapeHtml(s.ip)}</div></td>${['winrm','ssh','scanner'].map(k => `<td><span class="status-indicator ${p[k] ? 'online' : 'offline'}"><span class="agent-dot ${p[k] ? 'online' : 'offline'}"></span>${p[k] ? 'Open' : 'Closed'}</span></td>`).join('')}<td><span class="status-indicator ${s.reachable ? 'online' : 'offline'}">${s.reachable ? 'Reachable' : 'Unreachable'}</span></td></tr>`;
    }).join('');
  } catch (err) {
    const summary = document.getElementById('stationToolboxSummary');
    if (summary) summary.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><div class="empty-state-icon">⚠</div><div class="empty-state-title">Toolbox unavailable</div><div class="empty-state-desc">${escapeHtml(err.message)}</div></div>`;
  }
}
