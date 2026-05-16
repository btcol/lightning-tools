/* ============================================================
   Lightning Web Dashboard — app.js
   Lógica frontend: tabs, API calls, SSE streams, tablas
   ============================================================ */

'use strict';

// ── Utilidades generales ───────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const fmtSats = n => { n = parseInt(n)||0; return n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(1)+'k':String(n); };
const fmtMsat = n => { n = parseInt(n)||0; return fmtSats(Math.round(n/1000)); };

// Muestra una pequeña notificacion emergente (toast) en la esquina de la pantalla.
function toast(msg, type='info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  $('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// Añade una nueva linea de texto al final de un contenedor de logs especifico.
function logAppend(boxId, msg, cls='') {
  const box = $(boxId);
  if (!box) return;
  const line = document.createElement('span');
  if (cls) line.className = cls;
  line.textContent = msg + '\n';
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}

// Limpia todo el contenido de texto dentro de una caja de logs.
function logClear(boxId) {
  const box = $(boxId); if (box) box.innerHTML = '';
}

// Wrapper asincrono para fetch que maneja errores HTTP y parsea automaticamente JSON.
async function apiFetch(url, opts={}) {
  try {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } catch(e) {
    toast('Error: ' + e.message, 'err');
    return null;
  }
}

// Establece una conexion Server-Sent Events (SSE) y canaliza los mensajes a un logbox.
function sseConnect(url, logBoxId, onEnd) {
  const es = new EventSource(url);
  es.onmessage = e => {
    if (e.data === '__END__') { es.close(); if(onEnd) onEnd(); return; }
    const cls = e.data.includes('[ERROR]')||e.data.includes('[!]') ? 'log-err'
              : e.data.includes('[OK]') ? 'log-ok' : '';
    logAppend(logBoxId, e.data, cls);
  };
  es.onerror = () => { es.close(); logAppend(logBoxId,'[SSE desconectado]','log-warn'); if(onEnd) onEnd(); };
  return es;
}

// ── Navegación de pestañas ─────────────────────────────────────────────────

let cockpitGenerated = false;

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
    // Al entrar en cockpit, generar automáticamente si no se ha generado aún
    if (btn.dataset.tab === 'cockpit' && !cockpitGenerated) generateCockpit();
  });
});

// Solicita al backend la regeneracion del mapa 3D y lo carga en el iframe.
function generateCockpit() {
  logAppend('log-network', '[Cockpit] Generando HUD...');
  fetch(`/api/network/generate-cockpit?pubkey=${myPubkey||''}`)
    .then(r => {
      const reader = r.body.getReader(); const dec = new TextDecoder();
      function read() { reader.read().then(({done, value}) => {
        if (done) return;
        dec.decode(value).split('\n').forEach(l => {
          const m = l.replace(/^data: /,'').trim();
          if (!m) return;
          if (m === '__END__') {
            // Mostrar iframe, ocultar placeholder
            $('cockpit-placeholder').style.display = 'none';
            $('cockpit-iframe').style.display = 'block';
            $('cockpit-iframe').src = `/exports/lightning_cockpit.html?t=${Date.now()}`;
            cockpitGenerated = true;
            logAppend('log-network', '[Cockpit] HUD listo.', 'log-ok');
            return;
          }
          const cls = m.includes('[ERROR]') ? 'log-err' : m.includes('[OK]') ? 'log-ok' : '';
          logAppend('log-network', m, cls);
        });
        read();
      }); }
      read();
    }).catch(e => logAppend('log-network', '[Cockpit ERROR] '+e, 'log-err'));
}

// ── Estado global del nodo ─────────────────────────────────────────────────

let myPubkey = null;

// Llama al endpoint de info del nodo para verificar si LND esta online y poblar datos basicos.
async function detectNode() {
  const info = await apiFetch('/api/node/info');
  const el = $('node-status');
  if (info && info.identity_pubkey) {
    myPubkey = info.identity_pubkey;
    el.textContent = `[*] ${info.alias}  |  ${myPubkey.slice(0,16)}...  |  Altura: ${info.block_height}  |  Red: ${info.chains?.[0]?.network||'?'}`;
    el.className = 'online';
    // versión desde git (aproximada: usamos la fecha de buildtime del servidor)
    $('btcol-version').textContent = `Red: ${info.chains?.[0]?.network||'?'} | Alias: ${info.alias}`;
  } else {
    el.textContent = 'Nodo no detectado. ¿Está LND en ejecución?';
    el.className = 'offline';
  }
}

// ── TAB: Red & Cockpit ────────────────────────────────────────────────────

// Trae las estadisticas historicas y de salud del nodo para actualizar la grilla superior.
async function loadMetrics() {
  const s = await apiFetch('/api/node/metrics');
  if (!s) return;
  const snap = s.snap || {};
  const chA = snap.channels_active ?? '—', chT = snap.channels_total ?? '?';
  const liq  = snap.liquidity_ratio != null ? snap.liquidity_ratio.toFixed(1)+'%' : '—';
  const net7 = s.net_profit_7d_msat || 0;

  $('m-channels').textContent = `${chA} / ${chT}`;
  $('m-liq').textContent      = liq;
  $('m-cap').textContent      = fmtSats(snap.capacity_total || 0) + ' sats';
  $('m-earned').textContent   = fmtMsat(snap.fwd_fees_cum_msat || 0) + ' sat';
  $('m-paid').textContent     = fmtMsat(snap.payments_fees_cum_msat || 0) + ' sat';
  $('m-zombies').textContent  = snap.zombie_channels ?? '—';
  $('m-uptime').textContent   = (s.uptime_pct_7d || 0).toFixed(1) + '%';

  const netEl = $('m-net');
  netEl.textContent  = (net7 >= 0 ? '+' : '') + fmtMsat(Math.abs(net7)) + ' sat';
  netEl.className    = 'metric-val ' + (net7 >= 0 ? 'green' : 'red');
  const zmb = parseInt(snap.zombie_channels || 0);
  $('m-zombies').className = 'metric-val ' + (zmb > 0 ? 'red' : 'green');
}

$('btn-refresh-metrics').addEventListener('click', loadMetrics);

// ── Auto-escaneo ────────────────────────────────────────────
let autoScanTimer   = null;
let autoScanCountdown = 0;
let autoScanTicker  = null;

// Dispara el barrido de red profundo y maneja su conexion de streaming (SSE).
function runAutoScan() {
  if ($('btn-scan').disabled) return; // ya hay un escaneo en curso
  const hops = $('hops-select').value;
  $('btn-scan').disabled = true;
  logClear('log-network');
  logAppend('log-network', '[AUTO] Escaneo automático iniciado...');
  const es = new EventSource(`/api/network/scan?hops=${hops}`);
  es.onmessage = e => {
    if (e.data === '__END__') { 
      es.close(); 
      $('btn-scan').disabled = false; 
      logAppend('log-network', '[AUTO] Registrando snapshot de métricas...', 'log-info');
      // Registrar snapshot en la DB histórica
      sseConnect('/api/network/stats-snapshot', 'log-network', () => loadMetrics());
      return; 
    }
    const cls = e.data.includes('[ERROR]') ? 'log-err' : e.data.includes('[OK]') ? 'log-ok' : '';
    logAppend('log-network', e.data, cls);
  };
  es.onerror = () => { es.close(); $('btn-scan').disabled = false; };
}

// Inicia el temporizador (interval) que ejecuta el auto-escaneo ciclicamente.
function startAutoScan() {
  const secs = parseInt($('auto-scan-interval').value);
  autoScanCountdown = secs;
  if (autoScanTicker) clearInterval(autoScanTicker);
  autoScanTicker = setInterval(() => {
    autoScanCountdown--;
    const m = Math.floor(autoScanCountdown / 60), s = autoScanCountdown % 60;
    $('auto-scan-next').textContent = `Próximo: ${m}:${s.toString().padStart(2,'0')}`;
    if (autoScanCountdown <= 0) {
      autoScanCountdown = secs;
      runAutoScan();
    }
  }, 1000);
  $('auto-scan-next').textContent = `Próximo: ${Math.floor(secs/60)}:00`;
}

// Detiene el temporizador de auto-escaneo y limpia el indicador de proximo ciclo.
function stopAutoScan() {
  if (autoScanTicker) { clearInterval(autoScanTicker); autoScanTicker = null; }
  $('auto-scan-next').textContent = '';
}

$('auto-scan-toggle').addEventListener('change', e => {
  if (e.target.checked) {
    toast('Auto-escaneo activado', 'info');
    startAutoScan();
  } else {
    toast('Auto-escaneo desactivado', 'info');
    stopAutoScan();
  }
});

// Reiniciar timer si cambia el intervalo con el toggle activo
$('auto-scan-interval').addEventListener('change', () => {
  if ($('auto-scan-toggle').checked) startAutoScan();
});

$('btn-scan').addEventListener('click', () => {
  logClear('log-network');
  const hops = $('hops-select').value;
  $('btn-scan').disabled = true;
  sseConnect(`/api/network/scan?hops=${hops}`, 'log-network', () => {
    $('btn-scan').disabled = false;
    logAppend('log-network', '[INFO] Registrando snapshot de métricas...', 'log-info');
    sseConnect('/api/network/stats-snapshot', 'log-network', () => {
      loadMetrics();
      toast('Escaneo y Snapshot completados', 'ok');
    });
  });
});

// Cockpit: generación automática al entrar al tab (ver navegación de tabs arriba)
// El log del proceso va a log-network en la pestaña Red.

// ── TAB: Wallet ───────────────────────────────────────────────────────────

// Obtiene y muestra los saldos confirmados y pendientes de la wallet on-chain.
async function loadWalletBalance() {
  const d = await apiFetch('/api/wallet/balance');
  if (!d) return;
  $('w-conf').textContent   = (d.confirmed   || 0).toLocaleString() + ' sats';
  $('w-unconf').textContent = (d.unconfirmed || 0).toLocaleString() + ' sats';
  $('w-anchor').textContent = (d.reserved_anchor || 0).toLocaleString() + ' sats';
  const warn = d.confirmed < 50000 ? '[!] Saldo bajo — mantener >= 50,000 sats' : '';
  $('w-warn').textContent = warn;
}

// Solicita la lista de UTXOs disponibles y reconstruye la tabla HTML de la UI.
async function loadUTXOs() {
  const utxos = await apiFetch('/api/wallet/utxos');
  if (!utxos) return;
  const tbody = $('utxo-tbody');
  tbody.innerHTML = '';
  let total = 0;
  utxos.forEach(u => {
    total += u.amount_sat;
    const tr = document.createElement('tr');
    const txid = u.txid.length > 28 ? u.txid.slice(0,14)+'...'+u.txid.slice(-8) : u.txid;
    const confs = u.confirmations > 0 ? u.confirmations : 'mempool';
    const cls = u.confirmations > 0 ? 'td-green' : 'td-amber';
    tr.innerHTML = `<td class="mono">${txid}</td><td>${u.output_index}</td><td class="td-green">${u.amount_sat.toLocaleString()}</td><td class="${cls}">${confs}</td><td class="td-sub">${u.address_type}</td>`;
    tbody.appendChild(tr);
  });
  const warn = utxos.length >= 10 ? ' — [!] Alta fragmentación' : '';
  $('utxo-summary').textContent = `${utxos.length} UTXOs | ${total.toLocaleString()} sats${warn}`;
}

// Pide los metadatos del Static Channel Backup para mostrar su antiguedad.
async function loadSCBStatus() {
  const s = await apiFetch('/api/wallet/scb-status');
  if (!s) return;
  $('scb-auto').textContent   = s.auto?.path   ? `${s.auto.path} (hace ${s.auto.age_hours}h)` : 'No encontrado';
  $('scb-manual').textContent = s.manual?.name ? `${s.manual.name} (hace ${s.manual.age_hours}h)` : 'Ninguno';
}

// Agrupa y ejecuta todas las funciones de refresco de la pestaña Wallet On-chain.
function walletRefreshAll() { loadWalletBalance(); loadUTXOs(); loadSCBStatus(); }

$('btn-wallet-refresh').addEventListener('click', walletRefreshAll);

$('btn-gen-addr').addEventListener('click', async () => {
  const type = $('addr-type').value;
  const d = await apiFetch('/api/wallet/newaddress', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({type}) });
  if (d?.address) { $('new-addr').value = d.address; toast('Dirección generada', 'ok'); }
});

$('btn-copy-addr').addEventListener('click', () => {
  const a = $('new-addr').value;
  if (a) { navigator.clipboard.writeText(a); toast('Copiado', 'ok'); }
});

$('btn-scb-export').addEventListener('click', async () => {
  const d = await apiFetch('/api/wallet/scb-export', { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
  if (d) { toast(d.ok ? 'SCB exportado: '+d.file : 'Error exportando SCB', d.ok?'ok':'err'); loadSCBStatus(); }
});

$('btn-consolidate').addEventListener('click', () => {
  const dest = $('new-addr').value.trim();
  const fee  = parseInt($('cons-fee').value) || 2;
  if (!dest) { toast('Genera una dirección primero', 'err'); return; }
  if (!confirm(`Consolidar TODOS los UTXOs hacia:\n${dest}\nFee: ${fee} sat/vbyte\n\n¿Continuar?`)) return;
  logClear('log-wallet');
  sseConnect(`/api/wallet/consolidate`, 'log-wallet', () => { walletRefreshAll(); toast('Consolidación enviada','ok'); });
  // consolidate usa POST+SSE: workaround con fetch+ReadableStream
  fetch('/api/wallet/consolidate', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({dest_addr: dest, sat_per_vbyte: fee})
  }).then(r => {
    const reader = r.body.getReader(); const dec = new TextDecoder();
    function read() { reader.read().then(({done,value}) => {
      if(done) { walletRefreshAll(); return; }
      dec.decode(value).split('\n').forEach(l => { const m = l.replace(/^data: /,'').trim(); if(m && m!=='__END__') logAppend('log-wallet', m); });
      read();
    }); }
    read();
  }).catch(e => logAppend('log-wallet','[ERROR] '+e,'log-err'));
});

// ── TAB: Rebalanceo ───────────────────────────────────────────────────────

let currentSugs = [];

$('ratio-slider').addEventListener('input', e => {
  const v = e.target.value;
  $('ratio-display').textContent = `${v}/${100-v}`;
  localStorage.setItem('reb_ratio', v);
});

['bot-amt', 'bot-fee', 'bot-interval'].forEach(id => {
  $(id).addEventListener('input', e => localStorage.setItem('reb_' + id, e.target.value));
});

$('btn-calc-sugs').addEventListener('click', async () => {
  const ratio = $('ratio-slider').value;
  const sugs = await apiFetch(`/api/channels/suggestions?target_ratio=${ratio}`);
  if (!sugs) return;
  currentSugs = sugs;
  const tbody = $('sug-tbody');
  tbody.innerHTML = '';
  if (!sugs.length) { tbody.innerHTML = '<tr><td colspan="5" class="td-sub">Sin sugerencias. Verifica que haya canales activos.</td></tr>'; return; }
  sugs.forEach((s, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="td-green">${s.amount.toLocaleString()}</td><td class="mono">${s.from_scid}</td><td class="mono">${s.to_scid}</td><td class="td-alias">${s.from_peer}</td><td class="td-alias">${s.to_peer}</td>`;
    tr.addEventListener('click', () => {
      $('reb-from-scid').value = s.from_scid;
      $('reb-to-scid').value   = s.to_scid;
      $('reb-to-pub').value    = s.to_pub;
      $('reb-amt').value       = s.amount;
      tbody.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
      tr.classList.add('selected');
    });
    tbody.appendChild(tr);
  });
});

$('btn-simulate').addEventListener('click', async () => {
  const body = { amt_sats: parseInt($('reb-amt').value)||0, max_fee_sats: parseInt($('reb-fee').value)||100, max_fee_ppm: parseInt($('reb-ppm').value)||1000 };
  const res = await apiFetch('/api/rebalance/simulate', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
  if (!res) return;
  logAppend('log-rebalance', `--- Análisis de Rentabilidad ---`);
  logAppend('log-rebalance', `Fee esperado @ ${body.max_fee_ppm} ppm: ${res.fee_estimado?.toFixed(1)} sats`);
  logAppend('log-rebalance', `PPM si pagas el máximo: ${res.fee_ppm_if_max?.toFixed(0)} ppm`);
  logAppend('log-rebalance', res.ok ? '[OK] Fee dentro del límite.' : '[!] Fee supera el límite.', res.ok?'log-ok':'log-warn');
});

// Realiza una peticion POST via Fetch pero consumiendo la respuesta como un stream SSE (ReadableStream).
function ssePost(endpoint, payload, logBoxId, onEnd) {
  fetch(endpoint, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) })
    .then(r => {
      const reader = r.body.getReader(); const dec = new TextDecoder();
      function read() { reader.read().then(({done, value}) => {
        if(done) { if(onEnd) onEnd(); return; }
        dec.decode(value).split('\n').forEach(l => {
          const m = l.replace(/^data: /,'').trim();
          if (!m || m === '__END__') { if(m==='__END__' && onEnd) onEnd(); return; }
          const cls = m.includes('[ERROR]')||m.includes('[!]') ? 'log-err' : m.includes('[OK]') ? 'log-ok' : '';
          logAppend(logBoxId, m, cls);
        });
        read();
      }); }
      read();
    }).catch(e => { logAppend(logBoxId,'[ERROR] '+e,'log-err'); if(onEnd) onEnd(); });
}

$('btn-exec-reb').addEventListener('click', () => {
  const payload = { from_scid: $('reb-from-scid').value.trim(), to_pub: $('reb-to-pub').value.trim(), amt_sats: parseInt($('reb-amt').value)||0, max_fee_sats: parseInt($('reb-fee').value)||100 };
  if (!payload.from_scid || !payload.to_pub || payload.amt_sats <= 0) { toast('Faltan datos en el formulario','err'); return; }
  logClear('log-rebalance');
  $('btn-exec-reb').disabled = true;
  ssePost('/api/rebalance/execute', payload, 'log-rebalance', () => { $('btn-exec-reb').disabled = false; });
});

$('btn-clear-reb-log').addEventListener('click', () => logClear('log-rebalance'));

// ── Piloto Automático Experimental ─────────────────────────
let botES = null;  // EventSource activo del autopiloto

// Actualiza el color y texto de estado visual del Piloto Automatico de rebalanceo.
function setBotStatus(active) {
  const val = $('bot-status-val');
  val.textContent = active ? 'ACTIVO' : 'INACTIVO';
  val.style.color = active ? 'var(--green)' : 'var(--subtext)';
  $('bot-toggle').checked = active;
}

$('bot-toggle').addEventListener('change', async e => {
  if (e.target.checked) {
    // Activar
    const amt      = parseInt($('bot-amt').value)      || 1000;
    const fee      = parseInt($('bot-fee').value)      || 1;
    const interval = (parseInt($('bot-interval').value) || 5) * 60;
    const target   = parseInt($('ratio-slider').value) || 50;

    logClear('log-bot');
    logAppend('log-bot', '[BOT] Iniciando piloto automático...');
    setBotStatus(true);
    toast('Piloto automático ACTIVADO', 'info');

    // Abrir SSE vía fetch (POST) — el backend mantiene la conexión abierta
    try {
      const resp = await fetch('/api/rebalance/autopilot', {
        method: 'POST',
        headers: {'Content-Type': 'application/json',
                  'Authorization': 'Basic ' + btoa('admin:' + (localStorage.getItem('webpass') || 'lightning'))},
        body: JSON.stringify({amt_sats: amt, max_fee_sats: fee,
                              target_ratio: target, interval_secs: interval})
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        logAppend('log-bot', '[BOT ERROR] ' + (err.error || resp.status), 'log-err');
        setBotStatus(false);
        return;
      }
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      function readBot() {
        reader.read().then(({done, value}) => {
          if (done) { setBotStatus(false); return; }
          dec.decode(value).split('\n').forEach(l => {
            const m = l.replace(/^data: /, '').trim();
            if (!m || m === '__END__') { if (m === '__END__') setBotStatus(false); return; }
            const cls = m.includes('[OK]') ? 'log-ok' : m.includes('[ERROR]') || m.includes('[!]') ? 'log-err' : '';
            logAppend('log-bot', m, cls);
          });
          readBot();
        });
      }
      readBot();
    } catch(err) {
      logAppend('log-bot', '[BOT ERROR] ' + err, 'log-err');
      setBotStatus(false);
    }
  } else {
    // Detener
    logAppend('log-bot', '[BOT] Enviando señal de parada...');
    fetch('/api/rebalance/autopilot/stop', {method: 'POST'})
      .then(() => { setBotStatus(false); toast('Piloto automático DETENIDO', 'info'); });
  }
});

$('btn-clear-bot-log').addEventListener('click', () => logClear('log-bot'));

// ── TAB: Apertura Canales ─────────────────────────────────────────────────

let currentCands = [];

// Actualiza especificamente el campo de saldo enfocado en la pestaña de Apertura de Canales.
async function loadOpenWallet() {
  const d = await apiFetch('/api/wallet/balance');
  if (d) $('open-wallet-bal').textContent = (d.confirmed||0).toLocaleString() + ' sats confirmados';
}

$('btn-refresh-open-wallet').addEventListener('click', loadOpenWallet);

$('open-push').addEventListener('input', e => {
  $('push-warn').style.display = parseInt(e.target.value) > 0 ? '' : 'none';
});

$('btn-connect-only').addEventListener('click', async () => {
  const uri = $('ext-uri').value.trim();
  if (!uri || !uri.includes('@')) { toast('URI inválida (pubkey@ip:port)','err'); return; }
  const d = await apiFetch('/api/channels/connect', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({uri}) });
  if (d) {
    toast(d.ok ? 'Conectado' : 'Error: '+d.log?.slice(-1)?.[0], d.ok?'ok':'err');
    if (d.ok) $('open-pubkey').value = uri.split('@')[0];
  }
});

$('btn-connect-open').addEventListener('click', () => {
  const uri = $('ext-uri').value.trim();
  if (!uri || !uri.includes('@')) { toast('URI inválida','err'); return; }
  const push = parseInt($('open-push').value)||0;
  if (push > 0 && !confirm(`ATENCIÓN: Regalarás ${push.toLocaleString()} sats al nodo remoto.\n¿Continuar?`)) return;
  const payload = { pubkey: uri.split('@')[0], amt_sats: parseInt($('open-amt').value)||0, push_amt: push, host_uri: uri };
  logClear('log-open');
  $('btn-connect-open').disabled = true;
  ssePost('/api/channels/open', payload, 'log-open', () => { $('btn-connect-open').disabled = false; loadOpenWallet(); });
});

$('btn-scan-cands').addEventListener('click', async () => {
  const minC = parseInt($('cand-min-ch').value)||2;
  const maxD = parseInt($('cand-max-days').value)||30;
  const cands = await apiFetch(`/api/channels/candidates?min_channels=${minC}&max_days=${maxD}`);
  if (!cands) return;
  currentCands = cands;
  const tbody = $('cand-tbody');
  tbody.innerHTML = '';
  if (!cands.length) { tbody.innerHTML = '<tr><td colspan="5" class="td-sub">Sin candidatos. Ejecuta "Escanear Red" en la pestaña Red & Cockpit primero.</td></tr>'; return; }
  cands.forEach(c => {
    const tr = document.createElement('tr');
    const daysStr = c.days_ago < 9999 ? `hace ${c.days_ago}d` : 'nunca';
    tr.innerHTML = `<td class="td-alias">${c.alias}</td><td class="mono">${c.pubkey.slice(0,20)}...</td><td>${c.channels}</td><td class="td-green">${c.capacity.toLocaleString()}</td><td class="td-sub">${daysStr}</td>`;
    tr.addEventListener('click', () => { $('open-pubkey').value = c.pubkey; tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('selected')); tr.classList.add('selected'); });
    tbody.appendChild(tr);
  });
});

$('btn-open-channel').addEventListener('click', () => {
  const pubkey = $('open-pubkey').value.trim();
  const amt    = parseInt($('open-amt').value)||0;
  const push   = parseInt($('open-push').value)||0;
  if (!pubkey || amt <= 0) { toast('Pubkey y monto requeridos','err'); return; }
  if (push > 0 && !confirm(`ATENCIÓN: Regalarás ${push.toLocaleString()} sats.\n¿Continuar?`)) return;
  logClear('log-open');
  $('btn-open-channel').disabled = true;
  ssePost('/api/channels/open', {pubkey, amt_sats: amt, push_amt: push}, 'log-open', () => { $('btn-open-channel').disabled = false; loadOpenWallet(); });
});

$('btn-clear-open-log').addEventListener('click', () => logClear('log-open'));

// ── TAB: Cierre Canales ───────────────────────────────────────────────────

let closeChanList = [];

// Solicita el listado completo de canales (activos e inactivos) para la pestaña de Cierre.
async function loadAllChannels() {
  const chans = await apiFetch('/api/channels/all');
  if (!chans) return;
  closeChanList = chans;
  const tbody = $('close-tbody');
  tbody.innerHTML = '';
  chans.forEach(c => {
    const tr = document.createElement('tr');
    const st = c.status === 'OPEN' ? '<span class="badge badge-open">OPEN</span>'
             : c.status === 'PENDING_OPEN' ? '<span class="badge badge-pending">PENDING</span>'
             : '<span class="badge badge-close">'+c.status+'</span>';
    tr.innerHTML = `<td class="td-alias">${c.alias||'—'}</td><td class="mono">${c.pubkey.slice(0,16)}...</td><td>${st}</td><td class="td-green">${c.local.toLocaleString()}</td><td class="td-sub">${c.remote.toLocaleString()}</td><td class="mono" style="font-size:11px;">${c.chan_point}</td>`;
    tr.addEventListener('click', () => { $('close-chanpoint').value = c.chan_point; tbody.querySelectorAll('tr').forEach(r=>r.classList.remove('selected')); tr.classList.add('selected'); });
    tbody.appendChild(tr);
  });
}

$('btn-refresh-close').addEventListener('click', loadAllChannels);

$('btn-close-channel').addEventListener('click', () => {
  const chanpoint = $('close-chanpoint').value.trim();
  const force     = $('close-force').checked;
  if (!chanpoint) { toast('Selecciona un canal primero','err'); return; }
  if (force && !confirm('ATENCIÓN: Force Close bloqueará fondos temporalmente.\n¿Estás seguro?')) return;
  logClear('log-close');
  $('btn-close-channel').disabled = true;
  ssePost('/api/channels/close', {chan_point: chanpoint, force}, 'log-close', () => { $('btn-close-channel').disabled = false; loadAllChannels(); });
});

$('btn-clear-close-log').addEventListener('click', () => logClear('log-close'));

// ── Inicialización ────────────────────────────────────────────────────────

(async function init() {
  // Restaurar configuración de rebalanceo desde localStorage
  if (localStorage.getItem('reb_ratio')) $('ratio-slider').value = localStorage.getItem('reb_ratio');
  // Forzar sincronización visual (útil cuando el navegador restaura el input por sí solo)
  const ratioV = $('ratio-slider').value;
  $('ratio-display').textContent = `${ratioV}/${100-ratioV}`;

  ['bot-amt', 'bot-fee', 'bot-interval'].forEach(id => {
    if (localStorage.getItem('reb_' + id)) $(id).value = localStorage.getItem('reb_' + id);
  });

  await detectNode();
  await loadMetrics();
  walletRefreshAll();
  loadOpenWallet();
  loadAllChannels();
  // Auto-refresh métricas cada 5 min
  setInterval(loadMetrics, 300_000);
})();
