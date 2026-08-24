/**
 * app.js — Sat Set Tap Dashboard
 *
 * Semua komunikasi ke backend via:
 * - WebSocket /ws    → snapshot realtime (stats, anomali, network, forecast, log)
 * - fetch /api/*     → aksi (revoke, flush, import, export, lockdown, dll)
 *
 * Tidak ada logic bisnis di sini — hanya render dan kirim request ke API.
 */

'use strict';

// ── Chart setup ─────────────────────────────────────────────
const ctx      = document.getElementById('tapChart').getContext('2d');
const tapChart = new Chart(ctx, {
  type: 'bar',
  data: {
    labels: [],
    datasets: [
      { label: 'Masuk',   data: [], backgroundColor: 'rgba(64,160,43,.15)', borderColor: '#40a02b', borderWidth: 1 },
      { label: 'Ditolak', data: [], backgroundColor: 'rgba(210,15,57,.12)', borderColor: '#d20f39', borderWidth: 1 },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend:  { labels: { color: '#6c6f85', font: { family: 'Space Mono', size: 11 } } },
      tooltip: { backgroundColor: '#1a1a24', titleColor: '#cdd6f4', bodyColor: '#6c6f85' },
    },
    scales: {
      x: { ticks: { color: '#6c6f85', font: { size: 10, family: 'Space Mono' }, maxRotation: 45 }, grid: { color: '#2a2a3c' } },
      y: { ticks: { color: '#6c6f85', font: { size: 10, family: 'Space Mono' } }, grid: { color: '#2a2a3c' }, beginAtZero: true },
    },
  },
});
updateChartColors();

// ── State ────────────────────────────────────────────────────
let analyticsData    = null;
let currentGateView  = 'all';
let lockedGates      = [];
let tickerEvents     = [];
let allParticipants  = [];   // cache untuk filter lokal tanpa re-fetch


// ── WebSocket ────────────────────────────────────────────────
let ws;

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    document.getElementById('dot').classList.add('on');
    document.getElementById('ws-lbl').textContent = 'live';
  };

  ws.onclose = () => {
    document.getElementById('dot').classList.remove('on');
    document.getElementById('ws-lbl').textContent = 'reconnecting...';
    setTimeout(connect, 3000);
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    // Payload snapshot dikirim dari broadcast_loop setiap 1 detik
    if (msg.type === 'snapshot') {
      if (msg.anomaly)   updateAnomalySummary(msg.anomaly);  // set lockedGates dulu
      if (msg.stats)     updateStats(msg.stats);              // renderGates pakai lockedGates yang sudah update
      if (msg.analytics) renderChart(msg.analytics);      if (msg.network)   renderNetwork(msg.network);
      if (msg.forecast)  renderForecast(msg.forecast);
      if (msg.log)       { renderLog(msg.log); updateTickerFromLog(msg.log); }
    }
    // Pesan individual (backward compat / future use)
    if (msg.type === 'stats')            updateStats(msg.data);
    if (msg.type === 'analytics')        renderChart(msg.data);
    if (msg.type === 'anomaly_summary')  updateAnomalySummary(msg.data);
    if (msg.type === 'forecast')         renderForecast(msg.data);
    if (msg.type === 'network')          renderNetwork(msg.data);
    if (msg.type === 'new_event') {
      prependLog([msg.data]);
      tickerEvents.unshift(msg.data);
      if (tickerEvents.length > 3) tickerEvents.length = 3;
      updateTicker();
    }
  };
}

connect();


// ── Stats ────────────────────────────────────────────────────
function updateStats(d) {
  setVal('s-reg',   d.total_registered, 'c-reg');
  setVal('s-entry', d.total_entry,       'c-entry');
  setVal('s-total', d.total_tap,         'c-total');

  const gateCount   = Object.keys(d.gates || {}).length;
  const onlineCount = d.online_gates || 0;
  document.getElementById('s-gates').textContent     = `${onlineCount} / ${gateCount}`;
  document.getElementById('s-gates-sub').textContent = `${onlineCount} online · ${gateCount} total`;
  document.getElementById('s-time').textContent      = d.timestamp;

  if (d.stats && d.stats.suggestion) updateLB(d.stats);
  renderGates(d.gates || {});
  updateTicker();
}

function setVal(id, val, cardId) {
  const el = document.getElementById(id);
  if (parseInt(el.textContent) !== val) {
    el.textContent = val;
    const c = document.getElementById(cardId);
    if (c) { c.classList.remove('pop'); void c.offsetWidth; c.classList.add('pop'); }
  }
}

function renderGates(gates) {
  const maxTap = Math.max(...Object.values(gates).map(g => g.total_tap), 1);
  const grid   = document.getElementById('gates-grid');
  grid.innerHTML = '';

  for (const [name, info] of Object.entries(gates)) {
    const pct    = Math.round((info.total_tap / maxTap) * 100);
    const gidNum = name.replace('gate_', '');
    const locked = lockedGates.includes(parseInt(gidNum));
    const online = info.online === true;
    const dotStyle = online
      ? 'background:var(--accent);box-shadow:0 0 6px var(--accent);animation:pulse 2s infinite'
      : 'background:var(--muted)';

    const div = document.createElement('div');
    div.className = 'gate-card';
    if (locked) div.style.borderColor = 'var(--deny)';

    div.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div class="gate-name">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;${dotStyle}"></span>
          ${name.replace('_', ' ')}
        </div>
        ${locked ? '<span style="font-size:.6rem;color:var(--deny);font-weight:700">🔒 LOCKED</span>' : ''}
      </div>
      <div class="gate-num" style="color:${locked ? 'var(--deny)' : 'var(--text)'}">${info.total_tap}</div>
      <div class="gate-bar"><div class="gate-bar-fill" style="width:${pct}%;background:${locked ? 'var(--deny)' : 'var(--accent)'}"></div></div>
      <div class="gate-time">${info.last_seen ? info.last_seen.split('T')[1].slice(0,8) : '-'}</div>
      <div style="margin-top:.5rem;display:flex;gap:.4rem">
        ${locked
          ? `<button class="btn sm" style="border-color:var(--accent);color:var(--accent)" onclick="unlockGate(${gidNum})">Unlock</button>`
          : `<button class="btn danger sm" onclick="lockGate(${gidNum})">Lockdown</button>`
        }
      </div>`;
    grid.appendChild(div);
  }
}


// ── Load balance ─────────────────────────────────────────────
function updateLB(d) {
  const alert = document.getElementById('lb-alert');
  if (!d.suggestion) { alert.className = 'alert'; return; }
  document.getElementById('lb-title').textContent = d.suggestion.severity === 'high' ? '⚠ Gate Terlalu Ramai' : 'ℹ Distribusi Tidak Merata';
  document.getElementById('lb-msg').textContent   = d.suggestion.message;
  alert.className = `alert show ${d.suggestion.severity === 'high' ? '' : 'medium'}`;
}


// ── Ticker ────────────────────────────────────────────────────
function updateTickerFromLog(log) {
  tickerEvents = (log || []).slice(0, 3);
  updateTicker();
}

function updateTicker() {
  const c = document.getElementById('ticker-entries');
  if (!tickerEvents.length) {
    c.innerHTML = '<span class="text-muted">Menunggu event...</span>';
    return;
  }
  c.innerHTML = '<span style="color:var(--muted);margin-right:.5rem">&#10095;</span>' +
    tickerEvents.map(e => {
      const ts = (e.server_timestamp || e.timestamp || '').includes('T')
        ? (e.server_timestamp || e.timestamp || '').split('T')[1].slice(0, 8)
        : (e.server_timestamp || e.timestamp || '').slice(0, 8);
      const color = e.status === 'allowed' ? 'var(--accent)' : 'var(--deny)';
      return `<span class="ticker-item"><span class="ticker-ts">${ts}</span> <span class="ticker-gate">G${e.gate_id}</span> <span class="ticker-status" style="color:${color}">${e.status === 'allowed' ? 'ALLOW' : 'DENY'}</span></span>`;
    }).join('');
}


// ── Chart ─────────────────────────────────────────────────────
function setGateView(gate, btn) {
  currentGateView = gate;
  document.querySelectorAll('.tog').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (analyticsData) renderChart(analyticsData);
}

function renderChart(d) {
  analyticsData = d;
  tapChart.data.labels = d.labels.map(l => l.slice(-5));

  if (currentGateView === 'all') {
    tapChart.data.datasets[0].data  = d.all_allowed;
    tapChart.data.datasets[1].data  = d.all_denied;
    tapChart.data.datasets[0].label = 'Masuk (Semua)';
    tapChart.data.datasets[1].label = 'Ditolak (Semua)';
  } else {
    const gd = d.gates[currentGateView] || { allowed: [], denied: [] };
    tapChart.data.datasets[0].data  = gd.allowed;
    tapChart.data.datasets[1].data  = gd.denied;
    tapChart.data.datasets[0].label = `Masuk (${currentGateView.replace('_', ' ')})`;
    tapChart.data.datasets[1].label = `Ditolak (${currentGateView.replace('_', ' ')})`;
  }
  tapChart.update('none');

  // Tambahkan tombol toggle per gate yang belum ada
  const toggles  = document.getElementById('gate-toggles');
  const existing = new Set([...toggles.querySelectorAll('.tog')].map(b => b.dataset.gate));
  for (const gKey of Object.keys(d.gates || {})) {
    if (!existing.has(gKey)) {
      const b = document.createElement('button');
      b.className   = 'tog';
      b.dataset.gate = gKey;
      b.textContent  = gKey.replace('_', ' ').toUpperCase();
      b.onclick      = () => setGateView(gKey, b);
      toggles.appendChild(b);
    }
  }
}


// ── Log ───────────────────────────────────────────────────────
const STATUS_LABEL = {
  'allowed':             ['MASUK',       'allowed'],
  'denied_unregistered': ['TDK DAFTAR',  'denied_unregistered'],
  'denied_token_empty':  ['TOKEN HABIS', 'denied_token_empty'],
};

function formatTs(ts) {
  if (!ts) return '-';
  const t = ts.includes('T') ? ts.split('T')[1] : ts;
  return `<span>${t.slice(0, 8)}</span><span class="ms">${t.length > 8 ? t.slice(8) : ''}</span>`;
}

function makeRow(e, animate) {
  const tr     = document.createElement('tr');
  if (animate) tr.className = 'new-row';
  const status = e.status || 'allowed';
  const [label, cls] = STATUS_LABEL[status] || [status, 'allowed'];
  const tokenLeft = e.token_left !== undefined ? e.token_left : '-';
  const tokenMax  = e.token_max  !== undefined ? e.token_max  : '-';
  const ts = e.server_timestamp || e.timestamp || '-';

  tr.innerHTML = `
    <td><span class="badge ${cls}">${label}</span></td>
    <td>Gate ${e.gate_id}</td>
    <td class="uid">${e.ktp_uid}</td>
    <td style="color:var(--dim)">${e.name || '-'}</td>
    <td style="color:${status === 'allowed' ? 'var(--accent)' : 'var(--warn)'}">
      ${tokenLeft}/${tokenMax}
    </td>
    <td>${formatTs(ts)}</td>
    <td style="color:${e.crc_valid ? 'var(--accent)' : 'var(--warn)'}">${e.crc_valid ? 'OK' : 'FAIL'}</td>`;
  return tr;
}

function renderLog(entries) {
  const tb = document.getElementById('log-body');
  if (!tb) return;
  tb.innerHTML = '';
  if (!entries.length) {
    tb.innerHTML = '<tr><td colspan="7" class="empty-cell">Belum ada event.</td></tr>';
    return;
  }
  entries.forEach(e => tb.appendChild(makeRow(e, false)));
}

function prependLog(entries) {
  const tb = document.getElementById('log-body');
  if (tb.querySelector('td[colspan]')) tb.innerHTML = '';
  entries.forEach(e => tb.insertBefore(makeRow(e, true), tb.firstChild));
  while (tb.rows.length > 100) tb.deleteRow(tb.rows.length - 1);
}

async function refreshLog() {
  const res = await fetch('/api/log?limit=50');
  renderLog(await res.json());
}


// ── Participants ──────────────────────────────────────────────
async function loadParticipants() {
  const tbody = document.getElementById('participants-body');
  tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">Memuat...</td></tr>';
  try {
    const res  = await fetch('/api/register?limit=500');
    allParticipants = await res.json();
    renderParticipants(allParticipants);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-cell" style="color:var(--deny)">Gagal memuat: ${err.message}</td></tr>`;
  }
}

function renderParticipants(list) {
  const tbody = document.getElementById('participants-body');
  const count = document.getElementById('participants-count');
  const summary = document.getElementById('participant-summary');

  // ── Summary bar ──────────────────────────────────────────────
  const total      = list.length;
  const masuk      = list.filter(p => p.last_entry && p.last_entry !== '-').length;
  const belum      = total - masuk;
  const tokenHabis = list.filter(p => parseInt(p.token_left) <= 0).length;

  const summaryItems = [
    { label: 'Terdaftar',   val: total,       color: 'var(--dim)' },
    { label: 'Sudah Masuk', val: masuk,       color: 'var(--accent)' },
    { label: 'Belum Masuk', val: belum,       color: 'var(--muted)' },
    { label: 'Token Habis', val: tokenHabis,  color: tokenHabis > 0 ? 'var(--warn)' : 'var(--muted)' },
  ];

  if (summary) {
    summary.innerHTML = summaryItems.map(s => `
      <div style="background:var(--bg);border:1px solid var(--border);padding:.5rem .9rem;min-width:100px">
        <div style="font-size:.5rem;color:var(--muted);letter-spacing:.12em;text-transform:uppercase;margin-bottom:.2rem">${s.label}</div>
        <div style="font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:600;color:${s.color}">${s.val}</div>
      </div>`).join('');
  }

  count.textContent = `Menampilkan ${list.length} peserta`;

  // ── Table ─────────────────────────────────────────────────────
  if (!list.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-cell">Tidak ada peserta terdaftar.</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  for (const p of list) {
    const hasEntered = p.last_entry && p.last_entry !== '-';
    const tokenLeft  = p.token_left !== undefined ? p.token_left : '?';
    const tokenMax   = p.token_max  !== undefined ? p.token_max  : '?';
    const tokenEmpty = parseInt(tokenLeft) <= 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="uid">${p.uid || '-'}</td>
      <td>${p.name || '-'}</td>
      <td style="color:${tokenEmpty ? 'var(--warn)' : 'var(--accent)'}">
        ${tokenLeft}/${tokenMax}
        ${tokenEmpty ? '<span style="font-size:.5rem;color:var(--warn);margin-left:.3rem">HABIS</span>' : ''}
      </td>
      <td>
        <span class="badge ${hasEntered ? 'allowed' : 'denied_unregistered'}">
          ${hasEntered ? 'MASUK' : 'BELUM'}
        </span>
      </td>
      <td style="color:var(--dim)">${hasEntered ? p.last_entry.replace('T', ' ').slice(0, 19) : '-'}</td>
      <td style="color:var(--dim)">${(p.registered_at || '-').replace('T', ' ').slice(0, 19)}</td>
      <td>
        <button class="btn danger sm" onclick="revokeUidDirect('${p.uid}')">Revoke</button>
      </td>`;
    tbody.appendChild(tr);
  }
}

function filterParticipants(query) {
  const q = query.toLowerCase();
  const filtered = allParticipants.filter(p =>
    (p.uid  || '').toLowerCase().includes(q) ||
    (p.name || '').toLowerCase().includes(q)
  );
  renderParticipants(filtered);
}

async function revokeUid() {
  const input = document.getElementById('revoke-input');
  const uid   = input.value.trim().toUpperCase();
  if (uid.length !== 8 || !/^[0-9A-F]+$/.test(uid)) {
    showRevokeMsg('Format: 8 char hex (0-9 A-F)', 'var(--deny)');
    return;
  }
  await doRevoke(uid);
  input.value = '';
}

async function revokeUidDirect(uid) {
  if (!confirm(`Revoke UID ${uid}?\nData peserta akan dihapus permanen.`)) return;
  await doRevoke(uid);
}

async function doRevoke(uid) {
  if (!confirm(`Revoke UID ${uid}?\nData peserta akan dihapus permanen.`)) return;
  const btn = document.getElementById('revoke-btn');
  if (btn) { btn.textContent = '...'; btn.disabled = true; }
  try {
    const res  = await fetch(`/api/register/${uid}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) {
      showRevokeMsg(`UID ${uid} revoked`, 'var(--accent)');
      await loadParticipants();  // refresh tabel
    } else {
      showRevokeMsg(data.detail || 'Gagal revoke', 'var(--deny)');
    }
  } catch (err) {
    showRevokeMsg('Error: ' + err.message, 'var(--deny)');
  }
  if (btn) { btn.textContent = 'Revoke'; btn.disabled = false; }
  setTimeout(() => showRevokeMsg('', 'var(--dim)'), 3000);
}

function showRevokeMsg(text, color) {
  const el = document.getElementById('revoke-msg');
  if (el) { el.textContent = text; el.style.color = color; }
}

async function importCsv(input) {
  const file = input.files[0];
  if (!file) return;
  const statusEl = document.getElementById('import-status');
  statusEl.style.display = 'block';
  statusEl.style.color   = 'var(--dim)';
  statusEl.textContent   = `Mengupload ${file.name}...`;

  const form = new FormData();
  form.append('upload', file);
  try {
    const res  = await fetch('/api/register/import', { method: 'POST', body: form });
    const data = await res.json();
    if (res.ok) {
      statusEl.style.color = 'var(--accent)';
      statusEl.textContent = `✓ Import selesai: ${data.imported || 0} peserta ditambahkan, ${data.skipped || 0} dilewati`;
      await loadParticipants();
    } else {
      statusEl.style.color = 'var(--deny)';
      statusEl.textContent = '✗ ' + (data.detail || 'Gagal import');
    }
  } catch (err) {
    statusEl.style.color = 'var(--deny)';
    statusEl.textContent = '✗ Error: ' + err.message;
  }
  input.value = '';  // reset input supaya file yang sama bisa diupload lagi
  setTimeout(() => { statusEl.style.display = 'none'; }, 5000);
}

function exportCsv() {
  window.location.href = '/api/log/export';
}


// ── Flush ─────────────────────────────────────────────────────
async function flushEvent() {
  if (!confirm('Flush event log? Data registrasi tetap ada.')) return;
  await fetch('/api/flush-event', { method: 'DELETE' });
  document.getElementById('log-body').innerHTML =
    '<tr><td colspan="7" class="empty-cell">Event di-flush.</td></tr>';
  await loadParticipants();
}

async function flushAll() {
  if (!confirm('Flush SEMUA data termasuk registrasi? Tidak bisa di-undo.')) return;
  await fetch('/api/flush', { method: 'DELETE' });
  document.getElementById('log-body').innerHTML =
    '<tr><td colspan="7" class="empty-cell">Semua data di-flush.</td></tr>';
  allParticipants = [];
  renderParticipants([]);
}


// ── Gate controls ─────────────────────────────────────────────
async function lockGate(gateId) {
  if (!confirm(`Lockdown Gate ${gateId}? Semua tap akan ditolak.`)) return;
  await fetch(`/api/lockdown/${gateId}`, { method: 'POST' });
}

async function unlockGate(gateId) {
  await fetch(`/api/unlock/${gateId}`, { method: 'POST' });
}

async function unlockAll() {
  await fetch('/api/unlock/0', { method: 'POST' });
}


// ── Anomaly ───────────────────────────────────────────────────
const ANOMALY_ICONS = {
  TAILGATING:       '👤',
  UNKNOWN_FLOOD:    '🚨',
  GATE_SILENT:      '😶',
  RAPID_CROSS_GATE: '🔄',
};

function updateAnomalySummary(d) {
  lockedGates = d.locked_gates || [];
  const stat  = document.getElementById('anomaly-stat');
  const count = document.getElementById('anomaly-count');
  const msg   = document.getElementById('anomaly-stat-msg');

  count.textContent = `${d.total_active} anomali aktif`;

  if (d.total_active === 0) {
    stat.style.display = 'none';
    renderAnomalyList([]);
    return;
  }

  stat.style.display = 'flex';
  const parts = [];
  if (d.high)   parts.push(`${d.high} HIGH`);
  if (d.medium) parts.push(`${d.medium} MEDIUM`);
  msg.textContent = parts.join(' · ');

  renderAnomalyList(d.anomalies || []);
}

function renderAnomalyList(anomalies) {
  const list = document.getElementById('anomaly-list');
  if (!anomalies.length) {
    list.innerHTML = '<div class="no-anomaly">Tidak ada anomali — sistem aman ✓</div>';
    return;
  }
  list.innerHTML = '';
  for (const a of anomalies) {
    const div = document.createElement('div');
    div.className = 'anomaly-item';
    div.innerHTML = `
      <span class="anomaly-badge ${a.severity}">${a.severity}</span>
      <div>
        <div class="anomaly-msg">${ANOMALY_ICONS[a.type] || '⚠'} ${a.message}</div>
        <div class="anomaly-ts">${a.timestamp} · Gate ${a.gate_id ?? 'semua'} · ${a.type}</div>
      </div>`;
    list.appendChild(div);
  }
}

function addAnomalyToast(a) {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position:fixed;bottom:1.5rem;right:1.5rem;z-index:999;
    background:var(--surface);
    border:1px solid ${a.severity === 'high' ? 'var(--deny)' : 'var(--warn)'};
    padding:.75rem 1rem;font-size:.72rem;max-width:320px;animation:flash .3s`;
  toast.innerHTML = `<strong>${ANOMALY_ICONS[a.type] || '⚠'} ${a.type}</strong><br>${a.message}`;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
}


// ── Forecast ──────────────────────────────────────────────────
const CONF_LABEL = { high: 'HIGH', low: 'LOW', cold: 'COLD' };

function renderForecast(d) {
  const grid = document.getElementById('forecast-grid');
  if (!d || !d.gates || !Object.keys(d.gates).length) {
    grid.innerHTML = '<div class="text-muted">Tidak ada data...</div>';
    return;
  }

  const header = grid.parentNode.querySelector('summary');
  const st = d.status === 'cold' ? '⏳ Mengumpulkan data' : d.status === 'warming' ? '⚡ Pemanasan' : '✅ Siap';
  if (header) {
    let sb = header.querySelector('.forecast-status');
    if (!sb) { sb = document.createElement('span'); sb.className = 'forecast-status'; header.appendChild(sb); }
    sb.textContent  = ' [' + st + ']';
    sb.style.cssText = 'color:var(--dim);font-weight:400;font-size:.55rem';
  }

  grid.innerHTML = Object.entries(d.gates).map(([gid, g]) => {
    const isCold   = g.status === 'cold';
    const idleSec  = g.idle_seconds || 0;
    const idleM    = idleSec > 0 ? Math.floor(idleSec / 60) : 0;
    const idleLabel = idleM > 0 ? `🕐 idle ${idleM}m` : '';
    const dim      = idleSec > 300 ? 'opacity:.4' : idleSec > 120 ? 'opacity:.7' : '';
    const predColor = isCold ? 'var(--muted)' : g.severity === 'high' ? 'var(--deny)' : g.severity === 'medium' ? 'var(--warn)' : 'var(--accent)';
    const confCls   = g.confidence === 'high' ? 'allowed' : g.confidence === 'low' ? 'denied_token_empty' : 'denied_unregistered';
    return `
      <div style="background:var(--bg);border:1px solid var(--border);padding:.75rem;${isCold ? 'opacity:.7' : ''};${dim}">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:.55rem;color:var(--dim);letter-spacing:.1em;text-transform:uppercase">${gid.replace('_', ' ')}</span>
          <span class="badge ${confCls}" style="font-size:.45rem">${CONF_LABEL[g.confidence] || '-'}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:.75rem;margin:.4rem 0">
          <span style="font-size:.65rem;color:var(--muted)">Sekarang</span>
          <span style="font-family:'Syne',sans-serif;font-size:1.3rem;color:var(--text)">${g.current_tpm}</span>
          <span style="font-size:.55rem;color:var(--muted)">tpm</span>
          ${idleLabel ? `<span style="font-size:.5rem;color:var(--muted)">${idleLabel}</span>` : ''}
        </div>
        <div style="display:flex;align-items:baseline;gap:.75rem;margin:.2rem 0">
          <span style="font-size:.65rem;color:var(--muted)">Prediksi</span>
          <span style="font-family:'Syne',sans-serif;font-size:1.8rem;color:${predColor}">${g.predicted_tpm}</span>
          <span style="font-size:.55rem;color:var(--muted)">tpm</span>
        </div>
      </div>`;
  }).join('');

  if (d.recommendation) {
    let rc = document.getElementById('forecast-rec');
    if (!rc) {
      rc = document.createElement('div');
      rc.id = 'forecast-rec';
      rc.style.cssText = 'margin-top:.75rem;font-size:.65rem;color:var(--warn);background:var(--alert-bg);padding:.5rem .75rem;border:1px solid var(--warn)';
      grid.parentNode.appendChild(rc);
    }
    rc.textContent = '⏱ ' + d.recommendation;
    rc.style.display = d.status === 'cold' ? 'none' : '';
  }
}


// ── Network ───────────────────────────────────────────────────
function renderNetwork(d) {
  const grid    = document.getElementById('network-grid');
  const entries = Object.entries(d || {});
  if (!entries.length) {
    grid.innerHTML = '<div class="text-muted">Menunggu data jaringan...</div>';
    return;
  }
  grid.innerHTML = entries.map(([gid, g]) => {
    const lat      = g.latency;
    const rssi     = g.rssi;
    const rssiBars = rssi.avg >= -60 ? 4 : rssi.avg >= -80 ? 3 : rssi.avg >= -100 ? 2 : rssi.avg >= -110 ? 1 : 0;
    const bars     = '▮'.repeat(rssiBars) + '▯'.repeat(4 - rssiBars);
    const latColor = lat.current > 1000 ? 'var(--deny)' : lat.current > 500 ? 'var(--warn)' : 'var(--accent)';
    const sigColor = rssi.avg >= -80 ? 'var(--accent)' : rssi.avg >= -100 ? 'var(--warn)' : 'var(--deny)';
    return `
      <div style="background:var(--bg);border:1px solid var(--border);padding:.75rem">
        <div style="font-size:.55rem;color:var(--dim);letter-spacing:.1em;text-transform:uppercase">${gid.replace('_', ' ')}</div>
        <div style="display:flex;gap:1.5rem;margin-top:.5rem;flex-wrap:wrap">
          <div>
            <div style="font-size:.5rem;color:var(--muted);letter-spacing:.08em;text-transform:uppercase">Latency</div>
            <div style="font-size:1.2rem;color:${latColor}">${lat.current}<span style="font-size:.6rem;color:var(--dim)">ms</span></div>
            <div style="font-size:.55rem;color:var(--dim)">avg ${lat.avg} · max ${lat.max}</div>
          </div>
          <div>
            <div style="font-size:.5rem;color:var(--muted);letter-spacing:.08em;text-transform:uppercase">Signal</div>
            <div style="font-size:1rem;color:${sigColor}">${bars}</div>
            <div style="font-size:.55rem;color:var(--dim)">${rssi.avg} dBm avg</div>
          </div>
        </div>
        <div style="margin-top:.5rem;font-size:.55rem;color:var(--muted)">${lat.samples} sample(s)</div>
      </div>`;
  }).join('');
}


// ── Theme ─────────────────────────────────────────────────────
function setTheme(t) {
  const light = t === 'light';
  document.documentElement.classList.toggle('light', light);
  localStorage.setItem('theme', t);
  document.getElementById('theme-btn').textContent = light ? '🌙' : '☀️';
  updateChartColors();
}

function toggleTheme() {
  setTheme(document.documentElement.classList.contains('light') ? 'dark' : 'light');
}

function updateChartColors() {
  const get = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const ds  = tapChart.data.datasets;
  ds[0].backgroundColor = get('--chart-a-bg');
  ds[0].borderColor     = get('--chart-a-brd');
  ds[1].backgroundColor = get('--chart-d-bg');
  ds[1].borderColor     = get('--chart-d-brd');
  const o = tapChart.options;
  o.plugins.legend.labels.color      = get('--chart-leg');
  o.plugins.tooltip.backgroundColor  = get('--chart-tlbg');
  o.plugins.tooltip.titleColor       = get('--chart-tlt');
  o.plugins.tooltip.bodyColor        = get('--chart-tlb');
  o.scales.x.ticks.color = get('--chart-tk');
  o.scales.y.ticks.color = get('--chart-tk');
  o.scales.x.grid.color  = get('--chart-gd');
  o.scales.y.grid.color  = get('--chart-gd');
  tapChart.update('none');
}

// Restore saved theme
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'light') setTheme('light');
loadParticipants();
