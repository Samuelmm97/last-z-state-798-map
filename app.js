const canvas = document.getElementById('map');
const ctx = canvas.getContext('2d');
const shell = document.querySelector('.map-shell');
const list = document.getElementById('hqList');
const search = document.getElementById('search');
const alliance = document.getElementById('alliance');
const shield = document.getElementById('shield');
const terrain = document.getElementById('terrain');
const stateMembership = document.getElementById('stateMembership');
const minHq = document.getElementById('minHq');
const sort = document.getElementById('sort');
const allianceSort = document.getElementById('allianceSort');
const minParticipants = document.getElementById('minParticipants');
const minShare = document.getElementById('minShare');
const card = document.getElementById('hqCard');
const sidebar = document.getElementById('sidebar');
const radiusX = document.getElementById('radiusX');
const radiusY = document.getElementById('radiusY');
const radiusSize = document.getElementById('radiusSize');
const excludeNap = document.getElementById('excludeNap');
const pickRadiusPoint = document.getElementById('pickRadiusPoint');
const cache = new Map();
let metadata, hqs = [], filtered = [], selected = null;
let radiusPoint = { x: 500, y: 500 }, radius = 100, pickingPoint = false;
let activeZone = 'outside';
let allHqs = [], participationData = null;
let activeView = 'hqs', allianceStats = [], visibleAlliances = [], powerData = null, playerStats = [], visiblePlayers = [];
let centerX = 8000, centerY = 5250, scale = .08, fitted = false;
let width = 1, height = 1, framePending = false, dragging = null, displayLimit = 150;

const shieldLabels = {
  shielded: 'Shielded', unshielded: 'Unshielded', review: 'Needs review',
  not_applicable: 'Mud · N/A', not_hq: 'Not an HQ', unscanned: 'Not scanned'
};
const shieldStatus = hq => hq.shield?.status || 'unscanned';
const terrainStatus = hq => hq.shield?.terrain || 'unscanned';
const hasLocation = hq => Number.isFinite(hq?.x) && Number.isFinite(hq?.y);
// September 2026 alliance power ranking, limited to alliances recorded at the capital.
const nap13 = new Set(['Helm', 'SWT', 'WRtH', 'mERC', 'aTam', '4NG', 'UpS', 'Ayaa', 'E45Y', '7cie', 'SHSN', 'movR', 'ULD']);
const napTagAliases = { HeIm: 'Helm', '7cle': '7cie', '7cIe': '7cie' };
const isNap13 = tag => nap13.has(napTagAliases[tag] || tag);
// The three survivor boards share one {rank, value} shape, so a single loop renders all of them.
const powerMetrics = [['personal_power', 'personal power'], ['strongest_hero_power', 'strongest hero power'], ['total_hero_power', 'total hero power']];
// Board totals run into the hundreds of millions, so units keep the card and list rows readable.
const compactPower = value => {
  if (!Number.isFinite(value)) return '—';
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toLocaleString();
};
const filtersActive = () => Boolean(search.value.trim() || alliance.value || shield.value || terrain.value || Number(minHq.value));
const visiblePins = () => activeView === 'alliances' || activeView === 'players' || filtersActive() ? filtered : hqs;

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const mapX = x => x * metadata.scaleX;
const mapY = y => y * metadata.scaleY;
const screenX = x => (x - centerX) * scale + width / 2;
const screenY = y => (y - centerY) * scale + height / 2;
const worldAt = (sx, sy) => ({
  x: clamp(Math.round((centerX + (sx - width / 2) / scale) / metadata.scaleX), 0, 999),
  y: clamp(Math.round((centerY + (sy - height / 2) / scale) / metadata.scaleY), 0, 999)
});

function scheduleDraw() {
  if (!framePending) {
    framePending = true;
    requestAnimationFrame(() => { framePending = false; draw(); });
  }
}

function tile(level, x, y) {
  const key = `${level}/${x}/${y}`;
  if (cache.has(key)) {
    const result = cache.get(key);
    cache.delete(key); cache.set(key, result);
    return result;
  }
  const image = new Image();
  const result = { image, ready: false };
  image.onload = () => { result.ready = true; scheduleDraw(); };
  image.onerror = () => { result.failed = true; };
  image.src = `tiles/${key}.webp`;
  cache.set(key, result);
  while (cache.size > 320) cache.delete(cache.keys().next().value);
  return result;
}

function drawMap() {
  const level = clamp(Math.round(metadata.maxZoom + Math.log2(scale)), 0, metadata.maxZoom);
  const factor = 2 ** (metadata.maxZoom - level);
  const span = 256 * factor;
  const left = centerX - width / (2 * scale);
  const top = centerY - height / (2 * scale);
  const right = centerX + width / (2 * scale);
  const bottom = centerY + height / (2 * scale);
  const x0 = clamp(Math.floor(left / span), 0, Math.ceil(metadata.width / span) - 1);
  const x1 = clamp(Math.floor(right / span), 0, Math.ceil(metadata.width / span) - 1);
  const y0 = clamp(Math.floor(top / span), 0, Math.ceil(metadata.height / span) - 1);
  const y1 = clamp(Math.floor(bottom / span), 0, Math.ceil(metadata.height / span) - 1);
  for (let y = y0; y <= y1; y++) {
    for (let x = x0; x <= x1; x++) {
      const entry = tile(level, x, y);
      if (!entry.ready) continue;
      const tileWidth = Math.min(256, Math.ceil(metadata.width / factor) - x * 256);
      const tileHeight = Math.min(256, Math.ceil(metadata.height / factor) - y * 256);
      ctx.drawImage(entry.image, screenX(x * span), screenY(y * span),
                    tileWidth * factor * scale + .5, tileHeight * factor * scale + .5);
    }
  }
}

function drawOverlays() {
  if (document.getElementById('showGrid').checked) {
    ctx.strokeStyle = 'rgba(244,236,201,.32)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let n = 0; n <= 1000; n += 100) {
      const x = screenX(mapX(n)), y = screenY(mapY(n));
      ctx.moveTo(x, screenY(0)); ctx.lineTo(x, screenY(metadata.height));
      ctx.moveTo(screenX(0), y); ctx.lineTo(screenX(metadata.width), y);
    }
    ctx.stroke();
    ctx.strokeStyle = 'rgba(217,151,88,.9)';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 5]);
    ctx.beginPath();
    ctx.ellipse(screenX(mapX(500)), screenY(mapY(500)),
                100 * metadata.scaleX * scale, 100 * metadata.scaleY * scale, 0, 0, Math.PI * 2);
    ctx.stroke(); ctx.setLineDash([]);
  }
  if (document.getElementById('showPins').checked) {
    const radius = scale < .25 ? 1.4 : scale < .7 ? 2.3 : 3.1;
    for (const hq of visiblePins()) {
      const x = screenX(mapX(hq.x)), y = screenY(mapY(hq.y));
      if (x < -10 || x > width + 10 || y < -10 || y > height + 10) continue;
      ctx.fillStyle = hq.zone === 'capital' ? 'rgba(130,222,211,.9)' : 'rgba(255,223,149,.84)';
      ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill();
    }
  }
  const pointX = screenX(mapX(radiusPoint.x)), pointY = screenY(mapY(radiusPoint.y));
  ctx.strokeStyle = 'rgba(255,211,111,.95)'; ctx.fillStyle = 'rgba(255,211,111,.1)'; ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(pointX, pointY, radius * metadata.scaleX * scale, radius * metadata.scaleY * scale, 0, 0, Math.PI * 2);
  ctx.fill(); ctx.stroke();
  ctx.fillStyle = '#ffdc92'; ctx.strokeStyle = '#342817'; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.arc(pointX, pointY, 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  if (selected && hasLocation(selected)) {
    const x = screenX(mapX(selected.x)), y = screenY(mapY(selected.y));
    ctx.fillStyle = '#2a2117'; ctx.strokeStyle = '#ffe5a0'; ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(x, y, 10, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#ffe5a0'; ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
  }
}

function draw() {
  if (!metadata) return;
  const ratio = window.devicePixelRatio || 1;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.fillStyle = '#877f5b'; ctx.fillRect(0, 0, width, height);
  drawMap(); drawOverlays();
}

function resize() {
  width = shell.clientWidth; height = shell.clientHeight;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.ceil(width * ratio); canvas.height = Math.ceil(height * ratio);
  if (metadata && !fitted) fitMap(); else scheduleDraw();
}

function fitMap() {
  if (!metadata) return;
  centerX = metadata.width / 2; centerY = metadata.height / 2;
  scale = .94 * Math.min(width / metadata.width, height / metadata.height);
  fitted = true; scheduleDraw();
}

function zoomTo(next, sx = width / 2, sy = height / 2) {
  const beforeX = centerX + (sx - width / 2) / scale;
  const beforeY = centerY + (sy - height / 2) / scale;
  scale = clamp(next, .028, 2);
  centerX = beforeX - (sx - width / 2) / scale;
  centerY = beforeY - (sy - height / 2) / scale;
  scheduleDraw();
}

function refreshRadius() {
  if (!hqs.length) return;
  const radiusSquared = radius * radius;
  let count = 0, levelSum = 0, unreadable = 0;
  for (const hq of hqs) {
    if (shieldStatus(hq) === 'not_hq' || (excludeNap.checked && isNap13(hq.tag))) continue;
    const dx = hq.x - radiusPoint.x, dy = hq.y - radiusPoint.y;
    if (dx * dx + dy * dy > radiusSquared) continue;
    count++;
    if (Number.isFinite(hq.hq) && hq.hq > 0) levelSum += hq.hq;
    else unreadable++;
  }
  document.getElementById('radiusResults').textContent = `${count.toLocaleString()} HQs · ${levelSum.toLocaleString()} total HQ levels`;
  document.getElementById('radiusNote').textContent = `${unreadable ? `${unreadable} unreadable level${unreadable === 1 ? '' : 's'} omitted from level total · ` : ''}Circle includes HQs on its edge${excludeNap.checked ? ' · NAP 13 excluded' : ''}`;
  scheduleDraw();
}

function setRadiusPoint(x, y) {
  radiusPoint = { x, y };
  radiusX.value = x; radiusY.value = y;
  refreshRadius();
}

function setPickingPoint(value) {
  pickingPoint = value;
  pickRadiusPoint.setAttribute('aria-pressed', String(value));
  pickRadiusPoint.textContent = value ? 'Tap a point on the map…' : 'Pick point on map';
  canvas.classList.toggle('picking-point', value);
}

// Leaderboard rows are optional per HQ, so the block is rebuilt — or hidden — on every selection.
function fillCardPower(player) {
  const box = document.getElementById('cardPower');
  const grid = document.createElement('div');
  grid.className = 'power-grid';
  for (const [key, label] of powerMetrics) {
    const metric = player?.[key];
    if (!metric) continue;
    const cell = document.createElement('div');
    cell.className = 'power-metric';
    const caption = document.createElement('span');
    caption.textContent = `#${metric.rank} ${label}`;
    const value = document.createElement('strong');
    value.textContent = compactPower(metric.value);
    cell.append(caption, value);
    grid.append(cell);
  }
  const alliancePower = player?.tag && powerData?.alliances?.[player.tag]?.alliance_power;
  const notes = [];
  if (player?.hero) notes.push(`Strongest hero: ${player.hero}`);
  if (alliancePower) notes.push(`[${player.tag}] alliance power ${compactPower(alliancePower.value)} · #${alliancePower.rank}`);
  const note = document.createElement('div');
  note.className = 'power-note';
  note.textContent = notes.join(' · ');
  box.replaceChildren(grid, note);
  box.hidden = !grid.childElementCount && !notes.length;
}

function selectHQ(hq, jump = true) {
  selected = hq;
  if (hasLocation(hq)) setRadiusPoint(hq.x, hq.y);
  if ((hq.zone || 'outside') !== activeZone) setZone(hq.zone || 'outside');
  if (jump && hasLocation(hq)) { centerX = mapX(hq.x); centerY = mapY(hq.y); scale = Math.max(scale, .9); }
  document.getElementById('cardTag').textContent = hq.tag ? `[${hq.tag}]` : 'No alliance tag';
  document.getElementById('cardLevel').textContent = hq.hq ? `HQ ${hq.hq}` : 'HQ level unreadable';
  document.getElementById('cardName').textContent = hq.name;
  document.getElementById('cardLocation').textContent = hasLocation(hq) ? `X ${hq.x} · Y ${hq.y}` : 'Current map location unknown';
  const status = shieldStatus(hq);
  const cardShield = document.getElementById('cardShield');
  cardShield.className = `card-shield status-${status}`;
  cardShield.textContent = `Previous SvS shield: ${shieldLabels[status]}`;
  const observed = document.getElementById('cardObserved');
  if (hq.shield?.observedAt) {
    const time = new Date(hq.shield.observedAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
    observed.textContent = `SvS observation: ${time} · ${hq.shield.terrain === 'grass' ? 'Grass' : hq.shield.terrain === 'mud' ? 'Mud' : 'Terrain needs review'}${hq.shield.note ? ` · ${hq.shield.note}` : ''}`;
  } else observed.textContent = hq.shield?.note || 'No shield reading from the previous SvS.';
  observed.textContent += hasLocation(hq)
    ? ` · Location captured ${hq.observed_date || '2026-09-26'}${hq.current === false ? ' (not seen in latest sweep)' : ''}`
    : ' · No map location captured.';
  if (hq.roster_current) observed.textContent += ` · Roster confirmed by ${hq.roster_source || 'HQ leaderboard'} ${hq.roster_observed_date}`;
  const stateLabels = {listed_alliance:'Alliance appears on State 798 leaderboard',
    state_player_leaderboard:'State 798 player leaderboard confirms this player; current alliance is blank',
    likely_visitor:'Likely visitor: alliance absent from State 798 leaderboard; excluded from automatic placement',
    unconfirmed:'State alliance unconfirmed; excluded from automatic placement until reviewed'};
  if(hq.state_membership) observed.textContent += ` · ${stateLabels[hq.state_membership]} (${hq.state_checked_date})`;
  fillCardPower(hq.power);
  const image = document.getElementById('cardImage');
  const imageLink = document.getElementById('cardImageLink'); imageLink.hidden = !hq.photo;
  if (hq.photo) { image.src = hq.photo; imageLink.href = hq.photo; }
  image.alt = `In-game screenshot of ${hq.name}, HQ ${hq.hq}`;
  document.getElementById('cardSource').textContent = hq.source || `HQ leaderboard rank ${hq.leaderboard_rank}`;
  card.hidden = false;
  sidebar.classList.remove('open');
  document.querySelectorAll('.hq-row.active').forEach(element => element.classList.remove('active'));
  const row = document.querySelector(`.hq-row[data-id="${hq.id}"]`);
  if (row) row.classList.add('active');
  history.replaceState(null, '', `#hq-${hq.id}`);
  scheduleDraw();
}

function refreshList() {
  const query = search.value.trim().toLocaleLowerCase();
  if (activeView === 'alliances') {
    visibleAlliances = allianceStats.filter(item => item.tag.toLocaleLowerCase().includes(query)
      && item.inside >= Number(minParticipants.value)
      && item.inside / item.total * 100 >= Number(minShare.value));
    if (allianceSort.value === 'name') visibleAlliances.sort((a, b) => a.tag.localeCompare(b.tag));
    else if (allianceSort.value === 'percent') visibleAlliances.sort((a, b) => b.inside / b.total - a.inside / a.total || b.inside - a.inside || a.tag.localeCompare(b.tag));
    else visibleAlliances.sort((a, b) => b.inside - a.inside || b.inside / b.total - a.inside / a.total || a.tag.localeCompare(b.tag));
    const tags = new Set(visibleAlliances.map(item => item.tag));
    filtered = hqs.filter(hq => hq.zone === 'capital' && shieldStatus(hq) !== 'not_hq' && tags.has(hq.participation?.tag || hq.tag));
    renderAlliances();
    scheduleDraw();
    return;
  }
  if (activeView === 'players') {
    visiblePlayers = playerStats.filter(player => !query || `${player.name || ''} ${player.tag || ''} ${player.display || ''}`.toLocaleLowerCase().includes(query));
    // Pins follow the board so a selected row can be found where that survivor sits.
    const matched = new Set(visiblePlayers.map(player => player.atlas_id).filter(id => id != null));
    filtered = hqs.filter(hq => matched.has(hq.id) && shieldStatus(hq) !== 'not_hq');
    renderPlayers();
    scheduleDraw();
    return;
  }
  const allianceValue = alliance.value;
  filtered = hqs.filter(hq => {
    if ((hq.zone || 'outside') !== activeZone) return false;
    if (shieldStatus(hq) === 'not_hq' && shield.value !== 'not_hq') return false;
    const cohortTag = activeZone === 'capital' ? hq.participation?.tag || hq.tag : hq.tag;
    if (allianceValue === '__blank__' ? cohortTag : allianceValue && cohortTag !== allianceValue) return false;
    if (shield.value && shieldStatus(hq) !== shield.value) return false;
    if (terrain.value && terrainStatus(hq) !== terrain.value) return false;
    if (stateMembership.value && hq.state_membership !== stateMembership.value) return false;
    if ((hq.hq || 0) < Number(minHq.value)) return false;
    return !query || `${hq.name} ${hq.tag} ${hq.x},${hq.y}`.toLocaleLowerCase().includes(query);
  });
  if (sort.value === 'name') filtered.sort((a, b) => a.name.localeCompare(b.name));
  else if (sort.value === 'alliance') filtered.sort((a, b) => a.tag.localeCompare(b.tag) || a.name.localeCompare(b.name));
  else filtered.sort((a, b) => (b.hq || 0) - (a.hq || 0) || a.name.localeCompare(b.name));
  displayLimit = 150;
  renderList();
  scheduleDraw();
}

function renderAlliances() {
  const fragment = document.createDocumentFragment();
  for (const item of visibleAlliances) {
    const button = document.createElement('button');
    button.className = 'alliance-row';
    button.type = 'button';
    const tag = document.createElement('strong');
    tag.textContent = `[${item.tag}]`;
    const count = document.createElement('span');
    count.textContent = `${item.inside} / ${item.total}`;
    const share = document.createElement('span');
    share.className = 'alliance-share';
    share.textContent = `${(100 * item.inside / item.total).toFixed(1)}%`;
    button.append(tag, count, share);
    button.addEventListener('click', () => {
      activeView = 'hqs';
      search.value = '';
      alliance.value = item.tag;
      updateView();
    });
    fragment.append(button);
  }
  if (!visibleAlliances.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-results';
    empty.textContent = 'No alliances match these filters.';
    fragment.append(empty);
  }
  list.replaceChildren(fragment);
  document.getElementById('listCount').textContent = `${visibleAlliances.length} alliances`;
  document.getElementById('loadMore').hidden = true;
}

function renderPlayers() {
  const fragment = document.createDocumentFragment();
  for (const player of visiblePlayers) {
    const target = player.atlas_id != null ? hqs.find(hq => hq.id === player.atlas_id) : null;
    const button = document.createElement('button');
    // Only rows matched to an atlas HQ are worth a pointer and a jump; the rest are read-only.
    button.className = `player-row${target ? ' map-link' : ''}`;
    button.type = 'button';
    const rank = document.createElement('span');
    rank.className = 'player-rank';
    rank.textContent = player.personal_power?.rank ? `#${player.personal_power.rank}` : '—';
    const copy = document.createElement('span'); copy.className = 'copy';
    const name = document.createElement('span'); name.className = 'name';
    name.textContent = player.tag ? `[${player.tag}] ${player.name}` : player.name;
    const sub = document.createElement('span'); sub.className = 'sub';
    sub.textContent = powerMetrics.filter(([key]) => player[key])
      .map(([key, label]) => `${compactPower(player[key].value)} ${label}`).join(' · ') || 'No power metric published';
    copy.append(name, sub); button.append(rank, copy);
    if (target) {
      const pin = document.createElement('span');
      pin.className = 'pin';
      pin.textContent = target.hq ? String(target.hq) : '?';
      button.append(pin);
      button.addEventListener('click', () => {
        selectHQ(target);
        // selectHQ can switch zone tabs (and with them the view) when the HQ lies outside the capital.
        if (activeView !== 'players') { activeView = 'players'; updateView(); }
      });
    }
    fragment.append(button);
  }
  if (!visiblePlayers.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-results';
    empty.textContent = powerData ? 'No players match this search.' : 'No leaderboard capture has been published yet.';
    fragment.append(empty);
  }
  list.replaceChildren(fragment);
  document.getElementById('listCount').textContent = `${visiblePlayers.length} players`;
  document.getElementById('loadMore').hidden = true;
}

function renderList() {
  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-results';
    empty.textContent = 'No HQs match these filters.';
    list.replaceChildren(empty);
    document.getElementById('listCount').textContent = '0 matches';
    document.getElementById('loadMore').hidden = true;
    return;
  }
  const fragment = document.createDocumentFragment();
  for (const hq of filtered.slice(list.childElementCount, displayLimit)) {
    const button = document.createElement('button');
    button.className = `hq-row${selected && selected.id === hq.id ? ' active' : ''}`;
    button.type = 'button'; button.dataset.id = hq.id;
    const badge = document.createElement('span'); badge.className = 'pin'; badge.textContent = hq.hq ? String(hq.hq) : '?';
    const copy = document.createElement('span'); copy.className = 'copy';
    const name = document.createElement('span'); name.className = 'name'; name.textContent = hq.name;
    const sub = document.createElement('span'); sub.className = 'sub';
    sub.textContent = `${hq.tag ? `[${hq.tag}] · ` : ''}X ${hq.x} · Y ${hq.y}`;
    copy.append(name, sub); button.append(badge, copy);
    if (hq.shield) {
      const state = document.createElement('span');
      state.className = `shield-chip status-${shieldStatus(hq)}`;
      state.textContent = shieldLabels[shieldStatus(hq)];
      button.append(state);
    }
    button.addEventListener('click', () => selectHQ(hq));
    fragment.append(button);
  }
  if (list.childElementCount === 0) list.replaceChildren(fragment); else list.append(fragment);
  document.getElementById('listCount').textContent = `${filtered.length.toLocaleString()} matches`;
  document.getElementById('loadMore').hidden = list.childElementCount >= filtered.length;
}

function resetList() { list.replaceChildren(); refreshList(); }

function updateView() {
  if (activeView === 'alliances') activeZone = 'capital';
  for (const [name, id] of [['outside', 'outsideTab'], ['capital', 'capitalTab'], ['unknown', 'unknownTab']]) {
    const tab = document.getElementById(id);
    tab.classList.toggle('active', name === activeZone);
    tab.setAttribute('aria-selected', String(name === activeZone));
  }
  for (const [name, id] of [['hqs', 'hqViewTab'], ['alliances', 'allianceViewTab'], ['players', 'playerViewTab']]) {
    const tab = document.getElementById(id);
    tab.classList.toggle('active', name === activeView);
    tab.setAttribute('aria-selected', String(name === activeView));
  }
  document.getElementById('hqFilters').hidden = activeView !== 'hqs';
  document.getElementById('allianceFilters').hidden = activeView !== 'alliances';
  document.getElementById('playerFilters').hidden = activeView !== 'players';
  document.getElementById('searchLabel').textContent = activeView === 'alliances' ? 'Find an alliance' : activeView === 'players' ? 'Find a player' : 'Find an HQ';
  search.placeholder = activeView === 'alliances' ? 'Alliance tag' : activeView === 'players' ? 'Player name or tag' : 'Name, alliance, or X,Y';
  document.getElementById('listHeading').textContent = activeView === 'alliances' ? 'PREVIOUS SvS ALLIANCES' : activeView === 'players' ? 'POWER LEADERBOARDS' : activeZone === 'capital' ? 'PREVIOUS CAPITAL PARTICIPANTS' : activeZone === 'unknown' ? 'NO PRIOR SvS SCAN' : 'PREVIOUSLY OUTSIDE CAPITAL';
  document.getElementById('powerCaptureNote').textContent = powerData?.captured_date ? `Leaderboards captured ${powerData.captured_date}` : 'No leaderboard capture has been published yet.';
  resetList();
}

function setZone(zone) {
  activeZone = zone;
  if (zone !== 'capital') activeView = 'hqs';
  updateView();
}

canvas.addEventListener('pointerdown', event => {
  canvas.setPointerCapture(event.pointerId);
  dragging = { x: event.clientX, y: event.clientY, moved: false };
  canvas.classList.add('dragging');
});
canvas.addEventListener('pointermove', event => {
  const rect = canvas.getBoundingClientRect();
  if (metadata) {
    const world = worldAt(event.clientX - rect.left, event.clientY - rect.top);
    document.getElementById('mapCoords').textContent = `X: ${world.x} · Y: ${world.y}`;
  }
  if (!dragging) return;
  const dx = event.clientX - dragging.x, dy = event.clientY - dragging.y;
  if (Math.abs(dx) + Math.abs(dy) > 2) dragging.moved = true;
  centerX -= dx / scale; centerY -= dy / scale;
  dragging.x = event.clientX; dragging.y = event.clientY;
  scheduleDraw();
});
canvas.addEventListener('pointerup', event => {
  if (dragging && !dragging.moved && metadata) {
    const rect = canvas.getBoundingClientRect();
    const px = event.clientX - rect.left, py = event.clientY - rect.top;
    if (pickingPoint) {
      const point = worldAt(px, py);
      setRadiusPoint(point.x, point.y);
      setPickingPoint(false);
      dragging = null; canvas.classList.remove('dragging');
      return;
    }
    let closest = null, distance = 18 * 18;
    for (const hq of visiblePins()) {
      const dx = screenX(mapX(hq.x)) - px, dy = screenY(mapY(hq.y)) - py;
      const d = dx * dx + dy * dy;
      if (d < distance) { distance = d; closest = hq; }
    }
    if (closest) selectHQ(closest, false);
  }
  dragging = null; canvas.classList.remove('dragging');
});
canvas.addEventListener('pointercancel', () => { dragging = null; canvas.classList.remove('dragging'); });
canvas.addEventListener('wheel', event => {
  event.preventDefault();
  const rect = canvas.getBoundingClientRect();
  zoomTo(scale * (event.deltaY < 0 ? 1.24 : 1 / 1.24), event.clientX - rect.left, event.clientY - rect.top);
}, { passive: false });
document.getElementById('zoomIn').addEventListener('click', () => zoomTo(scale * 1.5));
document.getElementById('zoomOut').addEventListener('click', () => zoomTo(scale / 1.5));
document.getElementById('fitMap').addEventListener('click', fitMap);
document.getElementById('showPins').addEventListener('change', scheduleDraw);
document.getElementById('showGrid').addEventListener('change', scheduleDraw);
pickRadiusPoint.addEventListener('click', () => setPickingPoint(!pickingPoint));
for (const input of [radiusX, radiusY, radiusSize]) input.addEventListener('change', () => {
  const values = [radiusX, radiusY, radiusSize].map(item => Number(item.value));
  if (values.some(value => !Number.isInteger(value) || value < 0 || value > 999)) {
    radiusX.value = radiusPoint.x; radiusY.value = radiusPoint.y; radiusSize.value = radius;
    return;
  }
  radiusPoint = { x: values[0], y: values[1] };
  radius = values[2];
  refreshRadius();
});
excludeNap.addEventListener('change', refreshRadius);
document.getElementById('closeCard').addEventListener('click', () => { card.hidden = true; selected = null; scheduleDraw(); });
document.getElementById('menuButton').addEventListener('click', () => sidebar.classList.toggle('open'));
document.getElementById('loadMore').addEventListener('click', () => { displayLimit += 150; renderList(); });
document.getElementById('outsideTab').addEventListener('click', () => setZone('outside'));
document.getElementById('capitalTab').addEventListener('click', () => setZone('capital'));
document.getElementById('unknownTab').addEventListener('click', () => setZone('unknown'));
document.getElementById('hqViewTab').addEventListener('click', () => { activeView = 'hqs'; search.value = ''; updateView(); });
document.getElementById('allianceViewTab').addEventListener('click', () => { activeView = 'alliances'; search.value = ''; updateView(); });
document.getElementById('playerViewTab').addEventListener('click', () => { activeView = 'players'; search.value = ''; updateView(); });
search.addEventListener('input', resetList);
alliance.addEventListener('change', resetList);
stateMembership.addEventListener('change', resetList);
shield.addEventListener('change', () => {
  if (activeZone === 'outside' && shield.value && shield.value !== 'unscanned') setZone('capital');
  else resetList();
});
terrain.addEventListener('change', () => {
  if (activeZone === 'outside' && terrain.value && terrain.value !== 'unscanned') setZone('capital');
  else resetList();
});
minHq.addEventListener('change', resetList);
sort.addEventListener('change', resetList);
allianceSort.addEventListener('change', resetList);
minParticipants.addEventListener('change', resetList);
minShare.addEventListener('change', resetList);
document.getElementById('clearFilters').addEventListener('click', () => {
  search.value = ''; alliance.value = ''; shield.value = ''; terrain.value = ''; stateMembership.value = ''; minHq.value = '0';
  sort.value = 'hq'; allianceSort.value = 'count'; minParticipants.value = '1'; minShare.value = '0'; resetList();
});
window.addEventListener('resize', resize);

async function start() {
  try {
    const [mapResponse, hqResponse, shieldResponse, powerResponse, participationResponse] = await Promise.all([
      fetch('data/map.json'), fetch('data/hqs.json'), fetch('data/shields.json'),
      // The daily board import is optional: a 404 (nothing published yet) must leave the atlas untouched.
      fetch('data/power.json').catch(() => null),
      fetch('data/participation.json').catch(() => null)
    ]);
    if (!mapResponse.ok || !hqResponse.ok || !shieldResponse.ok) throw new Error('Map data could not be loaded');
    metadata = await mapResponse.json(); allHqs = await hqResponse.json();
    hqs = allHqs.filter(hq => hq.current !== false);
    if (participationResponse?.ok) participationData = await participationResponse.json().catch(() => null);
    const observations = await shieldResponse.json();
    if (powerResponse?.ok) powerData = await powerResponse.json().catch(() => null);
    const shieldById = new Map(observations.map(item => [item.id, item]));
    const participationById = new Map((participationData?.records || []).map(item => [item.id, item]));
    for (const hq of allHqs) {
      hq.shield = shieldById.get(hq.id) || null;
      hq.participation = participationById.get(hq.id) || null;
    }
    document.getElementById('mapCaptureNote').textContent = `Map captured ${metadata.captured_date || '2026-09-26'}`;
    const progressNote=document.getElementById('refreshProgressNote');
    if (metadata.refresh_progress) {
      progressNote.hidden=false;
      progressNote.textContent=metadata.refresh_progress;
    }
    document.getElementById('eventCaptureNote').textContent = `Shields and participation: previous SvS (${participationData?.captured_date || '2026-09-26'}).`;
    const playerRows = Object.values(powerData?.players || {});
    const powerById = new Map(playerRows.filter(item => item.atlas_id != null).map(item => [item.atlas_id, item]));
    for (const hq of allHqs) hq.power = powerById.get(hq.id) || null;
    // Rows arrive top-down from the game; anyone missing a personal-power entry sinks below the ranked.
    playerStats = playerRows.sort((a, b) => (b.personal_power?.value || 0) - (a.personal_power?.value || 0)
      || String(a.display || a.name || '').localeCompare(String(b.display || b.name || '')));
    const plausibleHqs = hqs.filter(hq => shieldStatus(hq) !== 'not_hq');
    document.getElementById('visibleCount').textContent = `${plausibleHqs.length.toLocaleString()} HQ candidates`;
    document.getElementById('outsideCount').textContent = plausibleHqs.filter(hq => (hq.zone || 'outside') === 'outside').length.toLocaleString();
    document.getElementById('capitalCount').textContent = plausibleHqs.filter(hq => hq.zone === 'capital').length.toLocaleString();
    const unknownCount = plausibleHqs.filter(hq => hq.zone === 'unknown').length;
    document.getElementById('unknownCount').textContent = unknownCount.toLocaleString();
    document.getElementById('unknownTab').hidden = !unknownCount;
    const totals = new Map(), inside = new Map();
    const eventHqs = (participationData?.records || plausibleHqs).filter(hq => shieldById.get(hq.id)?.status !== 'not_hq');
    for (const hq of eventHqs) {
      if (!hq.tag) continue;
      totals.set(hq.tag, (totals.get(hq.tag) || 0) + 1);
      if (hq.zone === 'capital') inside.set(hq.tag, (inside.get(hq.tag) || 0) + 1);
    }
    allianceStats = [...inside].map(([tag, count]) => ({ tag, inside: count, total: totals.get(tag) }));
    const tags = [...new Set([...plausibleHqs, ...eventHqs].map(hq => hq.tag).filter(Boolean))].sort((a,b) => a.localeCompare(b));
    const blank = document.createElement('option'); blank.value = '__blank__'; blank.textContent = 'No alliance tag';
    alliance.append(blank);
    for (const tag of tags) { const option = document.createElement('option'); option.value = tag; option.textContent = `[${tag}]`; alliance.append(option); }
    resetList(); resize(); refreshRadius();
    document.getElementById('loading').hidden = true;
    const deepLink = /^#hq-(\d+)$/.exec(location.hash);
    const linkedHq = deepLink && allHqs.find(hq => hq.id === Number(deepLink[1]));
    if (linkedHq) selectHQ(linkedHq);
  } catch (error) {
    document.getElementById('loading').textContent = `Unable to load the atlas: ${error.message}`;
  }
}
start();
