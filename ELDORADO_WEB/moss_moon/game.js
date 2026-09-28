(() => {
  'use strict';

  const SAVE_KEY = 'moss-moon-farm-v1';
  const LOCAL_FARM_BACKUP_KEY = 'moss-moon-farm-v1-local-backup';
  const PLOT_LIMIT = 50;
  const CROPS = {
    carrot: { name: 'Carrot', emoji: '🥕', seedEmoji: '🌱', seedCost: 18, seedLabel: 'Crunchy & quick', growMs: 180_000, value: 34, color: '#e9844d', leaf: '#6a9b57', mutation: 'Honey carrot', mutationEmoji: '🥕' },
    tomato: { name: 'Tomato', emoji: '🍅', seedEmoji: '🌿', seedCost: 38, seedLabel: 'A summer staple', growMs: 300_000, value: 76, color: '#d96655', leaf: '#568751', mutation: 'Sunblush tomato', mutationEmoji: '🍅' },
    moonberry: { name: 'Moonberry', emoji: '🫐', seedEmoji: '✨', seedCost: 88, seedLabel: 'A little magical', growMs: 540_000, value: 175, color: '#8284bd', leaf: '#527e69', mutation: 'Star-kissed berry', mutationEmoji: '🫐' },
    strawberry: { name: 'Strawberry', emoji: '🍓', seedEmoji: '🌸', seedCost: 52, seedLabel: 'Sweet & bright', growMs: 360_000, value: 92, color: '#d9576c', leaf: '#588651', mutation: 'Roseheart strawberry', mutationEmoji: '🍓' },
    pumpkin: { name: 'Pumpkin', emoji: '🎃', seedEmoji: '🍂', seedCost: 115, seedLabel: 'Patient & plentiful', growMs: 720_000, value: 210, color: '#e68a3e', leaf: '#57804d', mutation: 'Moonlit pumpkin', mutationEmoji: '🎃' },
    sunflower: { name: 'Sunflower', emoji: '🌻', seedEmoji: '☀️', seedCost: 78, seedLabel: 'A little golden', growMs: 480_000, value: 144, color: '#e6b842', leaf: '#5a8a52', mutation: 'Golden-hour sunflower', mutationEmoji: '🌻' },
    ember_chili: { name: 'Ember Chili', emoji: '🌶️', seedEmoji: '🌶️', seedCost: 180, seedLabel: 'Spicy and steady', growMs: 900_000, value: 360, color: '#d94f36', leaf: '#568751', mutation: 'Inferno Chili', mutationEmoji: '🔥' },
    frost_lily: { name: 'Frost Lily', emoji: '🪷', seedEmoji: '🪷', seedCost: 650, seedLabel: 'Cool nights, quiet growth', growMs: 3_600_000, value: 1_650, color: '#8fc6d8', leaf: '#5c8f78', mutation: 'Glacier Lily', mutationEmoji: '❄️' },
    blue_orchid: { name: 'Blue Orchid', emoji: '🪻', seedEmoji: '🪻', seedCost: 1200, seedLabel: 'Rare and brilliant', growMs: 7_200_000, value: 3800, color: '#667bd1', leaf: '#588651', mutation: 'Starlit Orchid', mutationEmoji: '💠' },
    golden_melon: { name: 'Golden Melon', emoji: '🍈', seedEmoji: '🍈', seedCost: 7500, seedLabel: 'A rich summer harvest', growMs: 21_600_000, value: 20000, color: '#d8bd53', leaf: '#588651', mutation: 'Sun-Crowned Melon', mutationEmoji: '🌟' },
    starfruit: { name: 'Starfruit', emoji: '⭐', seedEmoji: '⭐', seedCost: 25000, seedLabel: 'Slow-growing and precious', growMs: 36_000_000, value: 75000, color: '#e3c54b', leaf: '#588651', mutation: 'Comet Starfruit', mutationEmoji: '🌠' },
    nebula_wheat: { name: 'Nebula Wheat', emoji: '🌾', seedEmoji: '🌾', seedCost: 120000, seedLabel: 'A cosmic harvest', growMs: 432_000_000, value: 360000, color: '#b083d8', leaf: '#5a8a52', mutation: 'Starlit Wheat', mutationEmoji: '🌌' },
    rubyflower: { name: 'Rubyflower', emoji: '🌺', seedEmoji: '🌺', seedCost: 0, seedRubyCost: 35, seedLabel: 'Buy with Ruby · sells for Ruby', growMs: 3_600_000, value: 0, rubyValue: 40, color: '#cf426b', leaf: '#588651', mutation: 'Rubyflower Bloom', mutationEmoji: '💎' },
    diamond_bloom: { name: 'Diamond Bloom', emoji: '💠', seedEmoji: '💠', seedCost: 500000, seedLabel: 'A crystal crop · sells for Diamond', growMs: 864_000_000, value: 0, diamondValue: 1, color: '#68b6c8', leaf: '#588651', mutation: 'Prismatic Bloom', mutationEmoji: '🔷' }
  };
  const INITIAL_STATE = {
    gold: 560, diamond: 3, unlocked: 9, capacity: 24,
    seeds: { carrot: 7, tomato: 3, moonberry: 1, strawberry: 2, pumpkin: 1, sunflower: 2, ember_chili: 0, frost_lily: 0, blue_orchid: 0, golden_melon: 0, starfruit: 0, nebula_wheat: 0, rubyflower: 0, diamond_bloom: 0 }, produce: {}, selectedSeed: 'carrot',
    skills: { merchant: 0, greenThumb: 0, luckyPatch: 0, compost: 0, plotSurvey: 0, bigBasket: 0 }, plots: [], day: 1, lastVisit: Date.now(), playSeconds: 0, seenTip: false,
    goldEarnedToday: 0,
    pendingRubyAction: null, appliedRubyActions: []
  };
  let state = loadState();
  let walletRuby = null;
  let rubyWalletConnected = false;
  let farmConnected = false;
  let serverModeActive = false;
  let localFarmBackupReady = true;
  let accountId = '';
  let rubyActionInFlight = false;
  let characterCatalog = [];
  let characterPrices = {};
  let selectedCharacterId = '';
  let characterSearchQuery = '';
  let activeTab = 'farm';
  let selectedPlot = null;
  let animationFrame = 0;
  let lastSave = Date.now();
  let lastTick = Date.now();
  let lastUiUpdate = Date.now();
  let lastReadyCount = -1;
  let soundEnabled = false;
  let audioContext = null;

  const canvas = document.getElementById('farm-canvas');
  const ctx = canvas.getContext('2d');
  const ui = {
    gold: document.getElementById('gold-count'), ruby: document.getElementById('ruby-count'), diamond: document.getElementById('diamond-count'),
    day: document.getElementById('day-number'), season: document.getElementById('season-label'), canvas, panel: document.getElementById('panel-content')
  };

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(SAVE_KEY));
      if (!saved || saved.version !== 1) return structuredClone(INITIAL_STATE);
      const loaded = { ...structuredClone(INITIAL_STATE), ...saved,
        seeds: { ...INITIAL_STATE.seeds, ...saved.seeds }, produce: { ...saved.produce },
        skills: { ...INITIAL_STATE.skills, ...saved.skills },
        plots: Array.isArray(saved.plots) ? saved.plots : [],
        appliedRubyActions: Array.isArray(saved.appliedRubyActions) ? saved.appliedRubyActions : [] };
      delete loaded.ruby;
      return loaded;
    } catch { return structuredClone(INITIAL_STATE); }
  }

  function saveState() {
    if (serverModeActive && !localFarmBackupReady) return false;
    state.lastVisit = Date.now();
    try { localStorage.setItem(SAVE_KEY, JSON.stringify({ ...state, version: 1 })); return true; } catch { showToast('Your browser storage is full.'); return false; }
  }

  function preserveLocalFarmBackup() {
    try {
      if (!localStorage.getItem(LOCAL_FARM_BACKUP_KEY)) {
        const existing = localStorage.getItem(SAVE_KEY);
        if (existing) localStorage.setItem(LOCAL_FARM_BACKUP_KEY, existing);
      }
      return true;
    } catch {
      showToast('Could not archive the old local farm save; server farm is still available.');
      return false;
    }
  }

  function syncServerFarm(serverFarm) {
    if (!serverFarm || typeof serverFarm !== 'object') return;
    state.gold = Number(serverFarm.gold) || 0;
    state.diamond = Number(serverFarm.diamond) || 0;
    state.unlocked = Number(serverFarm.unlocked) || 9;
    state.capacity = Number(serverFarm.capacity) || 24;
    state.goldEarnedToday = Number(serverFarm.goldEarnedToday) || 0;
    state.seeds = { ...INITIAL_STATE.seeds, ...(serverFarm.seeds || {}) };
    state.produce = structuredClone(serverFarm.produce || {});
    state.skills = { ...INITIAL_STATE.skills, ...(serverFarm.skills || {}) };
    state.plots = Array.isArray(serverFarm.plots) ? structuredClone(serverFarm.plots) : [];
    while (state.plots.length < PLOT_LIMIT) state.plots.push(null);
    state.plots.length = PLOT_LIMIT;
  }

  function cropFor(plot) { return CROPS[plot?.crop] || null; }
  function stageFor(plot, now = Date.now()) {
    if (!plot?.crop) return 'empty';
    if (plot.ready) return 'ready';
    const elapsed = now - plot.plantedAt;
    const duration = cropFor(plot).growMs * Math.pow(0.91, state.skills.greenThumb);
    const fraction = Math.max(0, elapsed / duration);
    return fraction >= 1 ? 'ready' : fraction < 0.3 ? 'seedling' : fraction < 0.72 ? 'growing' : 'almost';
  }
  function plotAt(index) { return state.plots[index] || null; }
  function readyCount() { return state.plots.reduce((count, plot) => count + (plot?.crop && stageFor(plot) === 'ready' ? 1 : 0), 0); }
  function itemCount() { return Object.values(state.produce).reduce((sum, item) => sum + (item?.count || 0), 0); }
  function availableCapacity() { return Math.max(0, state.capacity - itemCount()); }
  function formatNumber(number) { return Math.floor(number).toLocaleString('en-US'); }
  function formatDuration(milliseconds) {
    const seconds = Math.max(1, Math.ceil(milliseconds / 1000));
    if (seconds >= 172800) return `${Math.round(seconds / 86400)}d`;
    if (seconds >= 7200) return `${Math.round(seconds / 3600)}h`;
    if (seconds >= 120) return `${Math.round(seconds / 60)}m`;
    return `${seconds}s`;
  }
  function currencyIcon(type) { return type === 'diamond' ? '✦' : type === 'ruby' ? '◆' : '◉'; }
  function cropRewardText(crop) {
    const rewards = [];
    if (crop.value > 0) rewards.push(`${formatNumber(crop.value)} Gold`);
    if (crop.rubyValue) rewards.push(`${formatNumber(crop.rubyValue)} Ruby`);
    if (crop.diamondValue) rewards.push(`${formatNumber(crop.diamondValue)} Diamond`);
    return rewards.join(' + ');
  }
  function produceRewardText(item) {
    const crop = CROPS[item.crop];
    if (!crop) return 'Harvest';
    const rewards = [];
    if (crop.value > 0) rewards.push(`${formatNumber(item.value)} Gold each`);
    if (crop.rubyValue) rewards.push(`${formatNumber(crop.rubyValue)} Ruby each`);
    if (crop.diamondValue) rewards.push(`${formatNumber(crop.diamondValue)} Diamond each`);
    return rewards.join(' + ');
  }
  function totalProduceRewardText() {
    const totals = Object.values(state.produce).reduce((sum, item) => {
      const crop = CROPS[item.crop];
      if (!crop) return sum;
      sum.gold += item.count * item.value;
      sum.ruby += item.count * crop.rubyValue;
      sum.diamond += item.count * crop.diamondValue;
      return sum;
    }, { gold: 0, ruby: 0, diamond: 0 });
    return [totals.gold && `${formatNumber(totals.gold)} Gold`, totals.ruby && `${formatNumber(totals.ruby)} Ruby`, totals.diamond && `${formatNumber(totals.diamond)} Diamond`].filter(Boolean).join(' + ');
  }
  function syncFarmClock() {
    const seconds = Math.floor(state.playSeconds % 120);
    document.getElementById('clock-label').textContent = `${String(8 + Math.floor(seconds / 20)).padStart(2, '0')}:${String((seconds % 20) * 3).padStart(2, '0')}`;
    document.getElementById('day-number').textContent = String(state.day).padStart(2, '0');
    document.getElementById('season-label').textContent = ['The first thaw', 'Soft rain days', 'Clover season', 'Long light'][Math.floor((state.day - 1) / 8) % 4];
    const weather = ['☀', '⛅', '☼', '✿'];
    document.getElementById('weather-icon').textContent = weather[Math.floor(state.playSeconds / 35) % weather.length];
    document.getElementById('weather-name').textContent = ['Mild & sunny', 'Clouds clearing', 'A little golden', 'Soft spring breeze'][Math.floor(state.playSeconds / 35) % 4];
  }

  function render() {
    ui.gold.textContent = farmConnected ? formatNumber(state.gold) : '…'; ui.ruby.textContent = walletRuby === null ? '…' : formatNumber(walletRuby); ui.diamond.textContent = farmConnected ? formatNumber(state.diamond) : '…';
    document.getElementById('ruby-wallet-label').textContent = rubyWalletConnected ? 'LINKED' : 'LOGIN';
    ui.ruby.title = rubyWalletConnected ? 'Shared RubyFarm wallet' : 'Sign in to RubyFarm to connect this wallet';
    document.getElementById('plot-count').textContent = state.unlocked;
    document.getElementById('storage-tab-count').textContent = itemCount();
    document.getElementById('storage-dot').classList.toggle('hidden', readyCount() === 0);
    document.getElementById('ready-count').textContent = readyCount();
    document.getElementById('harvest-all-button').disabled = !farmConnected || Boolean(state.pendingRubyAction) || readyCount() === 0 || availableCapacity() === 0;
    const nextPrice = plotPrice();
    document.getElementById('plot-price').textContent = state.unlocked >= PLOT_LIMIT ? 'MAX' : formatNumber(nextPrice);
    document.getElementById('unlock-plot-button').disabled = !farmConnected || Boolean(state.pendingRubyAction) || state.gold < nextPrice || state.unlocked >= PLOT_LIMIT;
    document.getElementById('unlock-plot-button').title = state.unlocked >= PLOT_LIMIT ? 'You have all 50 patches!' : `Unlock a patch for ${nextPrice} gold`;
    document.querySelectorAll('.rail-button[data-tab], .panel-tab[data-tab]').forEach(button => button.classList.toggle('active', button.dataset.tab === activeTab));
    renderSeeds(); renderPanel(); syncFarmClock();
  }

  function renderSeeds() {
    const container = document.getElementById('seed-options');
    container.innerHTML = Object.entries(CROPS).map(([key, crop]) => `
      <button class="seed-choice ${state.selectedSeed === key ? 'selected' : ''}" data-seed="${key}" title="Plant ${crop.name} (${state.seeds[key] || 0} seeds)" ${!farmConnected || state.pendingRubyAction || !state.seeds[key] ? 'disabled' : ''}>
        <span class="seed-emoji">${crop.seedEmoji}</span><span class="seed-meta"><strong>${crop.name}</strong><small>${state.seeds[key] || 0} seeds</small></span>
      </button>`).join('');
  }

  function renderPanel() {
    if (activeTab === 'farm') renderOverview();
    if (activeTab === 'storage') renderStorage();
    if (activeTab === 'shop') renderShop();
    if (activeTab === 'skills') renderSkills();
  }

  function renderOverview() {
    const planted = state.plots.filter(plot => plot?.crop).length;
    const ready = readyCount();
    const next = state.plots.findIndex((plot, index) => index < state.unlocked && plot?.crop && stageFor(plot) !== 'ready');
    const nextPlot = next >= 0 ? state.plots[next] : null;
    const crop = cropFor(nextPlot);
    const remaining = nextPlot && crop ? Math.max(0, crop.growMs * Math.pow(0.91, state.skills.greenThumb) - (Date.now() - nextPlot.plantedAt)) : 0;
    const grid = Array.from({ length: PLOT_LIMIT }, (_, index) => {
      if (index >= state.unlocked) return '<span class="mini-plot locked"></span>';
      const plot = plotAt(index); const stage = stageFor(plot);
      return `<span class="mini-plot ${stage === 'ready' ? 'ready' : stage === 'empty' ? '' : 'growing'}"></span>`;
    }).join('');
    ui.panel.innerHTML = `<div class="panel-title-row"><div><h2>At a glance</h2><div class="panel-kicker">A little overview of your patch</div></div><span class="quiet-icon">✿</span></div>
      <div class="overview-stat"><div class="overview-stat-top"><strong>Growing & glowing</strong><span>${planted} / ${state.unlocked} planted</span></div><div class="mini-plots">${grid}</div><div class="progress-caption"><span>${ready ? `${ready} ready to gather` : 'Every little seed counts'}</span><strong>${ready} ready</strong></div></div>
      <div class="overview-stat"><div class="overview-stat-top"><strong>Your land</strong><span>${state.unlocked} / ${PLOT_LIMIT} patches</span></div><div class="progress-track"><span style="width:${Math.round(state.unlocked / PLOT_LIMIT * 100)}%"></span></div><div class="progress-caption"><span>Room for more dreams</span><strong>${Math.round(state.unlocked / PLOT_LIMIT * 100)}%</strong></div></div>
      <div class="overview-stat"><div class="overview-stat-top"><strong>Next little harvest</strong><span>${nextPlot ? crop.emoji : '🌾'}</span></div><div class="progress-track"><span style="width:${nextPlot ? Math.min(98, Math.round((1 - remaining / (crop.growMs * Math.pow(0.91, state.skills.greenThumb))) * 100)) : 0}%"></span></div><div class="progress-caption"><span>${nextPlot ? `${crop.name} is reaching for the sun` : 'Plant something lovely'}</span><strong>${nextPlot ? formatDuration(remaining) : 'Ready'}</strong></div></div>
      <div class="overview-stat"><div class="overview-stat-top"><strong>Gold earned today</strong><span>${Math.round((state.goldEarnedToday || 0) / goldCapToday() * 100)}%</span></div><div class="progress-track"><span style="width:${Math.min(100, (state.goldEarnedToday || 0) / goldCapToday() * 100)}%"></span></div><div class="progress-caption"><span>Daily cap at ${state.unlocked} patches</span><strong>${(state.goldEarnedToday || 0).toLocaleString()} / ${goldCapToday().toLocaleString()}</strong></div></div>
      <div class="callout"><span class="callout-icon">✦</span><p><strong>Little wonder:</strong> crops sometimes grow a rare mutation. A sprinkle of luck makes those surprises more likely!</p></div>`;
  }

  function renderStorage() {
    const used = itemCount();
    const products = Object.entries(state.produce).filter(([, item]) => item.count > 0);
    const items = products.length ? `<div class="item-list">${products.map(([key, item]) => `<div class="inventory-row"><span class="item-emoji">${item.emoji}</span><span class="item-info"><strong>${item.name}</strong><small>${produceRewardText(item)}</small></span><span class="item-qty">× ${item.count}</span><button class="sell-button" data-sell="${key}" ${!farmConnected || state.pendingRubyAction ? 'disabled' : ''}>Sell</button></div>`).join('')}</div>` : `<div class="empty-storage"><span>🧺</span><strong>A little room to grow</strong><p>Your harvested crops will find a cozy home here.</p></div>`;
    ui.panel.innerHTML = `<div class="panel-title-row"><div><h2>Pantry & shed</h2><div class="panel-kicker">A home for everything you gather</div></div><span class="quiet-icon">▤</span></div>
      <div class="storage-capacity"><div class="overview-stat-top"><strong>Pantry space</strong><span>${used} / ${state.capacity}</span></div><div class="progress-track"><span style="width:${Math.min(100, used / state.capacity * 100)}%"></span></div><div class="progress-caption"><span>${availableCapacity()} spaces left</span><span class="storage-buttons"><button class="upgrade-button" data-storage="gold" ${!farmConnected || state.pendingRubyAction || state.capacity >= 100 || state.gold < 240 ? 'disabled' : ''}>Expand · 240 ◉</button><button class="upgrade-button" data-storage="diamond" ${!farmConnected || state.pendingRubyAction || state.capacity >= 100 || state.diamond < 2 ? 'disabled' : ''}>+12 · 2 ✦</button></span></div></div>
      <div class="section-label" style="margin-bottom:9px">HARVESTED GOODIES</div>${items}
      ${products.length ? `<button class="sell-button" id="sell-all-button" style="width:100%;margin-top:13px;padding:10px" ${!farmConnected || state.pendingRubyAction ? 'disabled' : ''}>Sell all · ${totalProduceRewardText()}<small style="display:block;font-weight:400;opacity:.8">gold left to sell today: ${goldRoomToday().toLocaleString()}</small></button>` : ''}
      <div class="section-label" style="margin:18px 0 8px">SEED POUCH</div><div class="item-list">${Object.entries(CROPS).map(([key, crop]) => `<div class="inventory-row"><span class="item-emoji">${crop.seedEmoji}</span><span class="item-info"><strong>${crop.name} seeds</strong><small>${crop.seedLabel}</small></span><span class="item-qty">× ${state.seeds[key] || 0}</span></div>`).join('')}</div>`;
  }

  function renderShop() {
    ui.panel.innerHTML = `<div class="panel-title-row"><div><h2>Village market</h2><div class="panel-kicker">Seeds, storage & good ideas</div></div><span class="quiet-icon">♧</span></div><div class="section-label">FRESH SEEDS</div>
      <div class="shop-section">${Object.entries(CROPS).map(([key, crop]) => { const rubySeed = Boolean(crop.seedRubyCost); const goldPrice = seedPrice(key); const priceLabel = rubySeed ? `${formatNumber(crop.seedRubyCost)} ◆ Ruby` : `${formatNumber(goldPrice)} ◉ Gold${goldPrice < crop.seedCost ? ` <s>${formatNumber(crop.seedCost)}</s>` : ''}`; const canBuy = rubySeed ? walletRuby >= crop.seedRubyCost : state.gold >= goldPrice; return `<div class="shop-card"><span class="shop-art">${crop.seedEmoji}</span><span class="shop-info"><strong>${crop.name} seeds</strong><small>${crop.seedLabel} · grows in ${formatDuration(crop.growMs)}</small><span class="shop-price">${priceLabel} each · ${state.seeds[key] || 0} owned</span></span><button class="buy-button" data-buy-seed="${key}" ${!farmConnected || state.pendingRubyAction || !canBuy ? 'disabled' : ''}>Buy 1</button></div>`; }).join('')}</div>
      <div class="callout"><span class="callout-icon">✦</span><p>Not just a pretty face: rare crop mutations sell for <strong>3× more gold</strong>. Keep an eye out!</p></div>
      <section class="character-shop" aria-label="Character shop">
        <div class="section-label">CHARACTER SHOP · DELIVERY TO ACCOUNT MAILBOX</div>
        <input id="character-search" type="search" placeholder="Search characters by name or ID" value="${characterSearchQuery.replace(/[&<>"']/g, '')}">
        <select id="character-select" aria-label="Choose a character">
          <option value="">${characterCatalog.length ? 'Choose a character…' : 'Sign in to load characters'}</option>
          ${characterCatalog.filter(character => {
            const query = characterSearchQuery.trim().toLowerCase();
            return !query || character.name.toLowerCase().includes(query) || String(character.id).includes(query);
          }).map(character => `<option value="${character.id}" ${String(selectedCharacterId) === String(character.id) ? 'selected' : ''}>${character.name} · ${character.star}★ · #${character.id}</option>`).join('')}
        </select>
        <div class="character-purchase-row">
          <span id="character-price">Select a character to view its price</span>
          <button class="buy-button" id="buy-character-button" ${!farmConnected || !selectedCharacterId || state.pendingRubyAction ? 'disabled' : ''}>Buy</button>
        </div>
        <div class="character-shop-message" id="character-shop-message" aria-live="polite"></div>
      </section>
      <div class="section-label" style="margin-top:18px">USEFUL THINGS</div><div class="shop-card"><span class="shop-art">🎁</span><span class="shop-info"><strong>Golden care package</strong><small>3 carrots, 2 tomatoes, and a ruby</small><span class="shop-price">◆ 3 shared ruby</span></span><button class="buy-button" data-care-package ${!farmConnected || walletRuby === null || walletRuby < 3 || state.pendingRubyAction ? 'disabled' : ''}>Get</button></div>`;
    renderCharacterPrice();
    document.getElementById('character-search').addEventListener('input', event => {
      characterSearchQuery = event.target.value;
      renderPanel();
      const search = document.getElementById('character-search');
      search.focus();
      search.setSelectionRange(search.value.length, search.value.length);
    });
    document.getElementById('character-select').addEventListener('change', event => {
      selectedCharacterId = event.target.value;
      renderPanel();
    });
  }

  function renderCharacterPrice() {
    const priceNode = document.getElementById('character-price');
    const buyButton = document.getElementById('buy-character-button');
    if (!priceNode || !buyButton) return;
    const character = characterCatalog.find(entry => String(entry.id) === String(selectedCharacterId));
    if (!character) {
      priceNode.textContent = 'Select a character to view its price';
      buyButton.disabled = true;
      return;
    }
    const price = characterPrices[String(character.star)] || { gold: '0', ruby: '0' };
    const goldCost = Number(price.gold) || 0;
    const rubyCost = Number(price.ruby) || 0;
    priceNode.textContent = `${formatNumber(goldCost)} farm Gold${rubyCost ? ` + ${formatNumber(rubyCost)} Ruby` : ''} · ${character.star}★`;
    buyButton.disabled = !farmConnected || state.pendingRubyAction !== null
      || state.gold < goldCost || walletRuby < rubyCost;
  }

  function skillCost(key, level) {
    if (key === 'merchant') return { type: 'gold', amount: 180 + level * 220 };
    if (key === 'greenThumb') return { type: 'diamond', amount: 1 + Math.floor(level / 2) };
    if (key === 'compost') return { type: 'gold', amount: [300, 1500, 7500][level] };
    if (key === 'plotSurvey') return { type: 'gold', amount: [1000, 4000, 16000][level] };
    if (key === 'bigBasket') return { type: 'gold', amount: [400, 1200, 3600, 9000, 22000][level] };
    return { type: 'ruby', amount: 3 + level * 2 };
  }
  const SKILL_MAX = { merchant: 5, greenThumb: 5, luckyPatch: 5, compost: 3, plotSurvey: 3, bigBasket: 5 };
  const DAILY_GOLD_CAP = 600000;
  const DAILY_GOLD_CAP_FLOOR = 120000;
  function goldCapToday() {
    const span = Math.max(0, Math.min(1, (state.unlocked - 9) / 41));
    return Math.floor(Math.min(DAILY_GOLD_CAP, DAILY_GOLD_CAP_FLOOR + (DAILY_GOLD_CAP - DAILY_GOLD_CAP_FLOOR) * Math.pow(span, 2.4)) / 100) * 100;
  }
  function goldRoomToday() { return Math.max(0, goldCapToday() - (state.goldEarnedToday || 0)); }
  function hasFunds(cost) { return cost.type === 'ruby' ? walletRuby !== null && walletRuby >= cost.amount : state[cost.type] >= cost.amount; }
  function renderSkills() {
    const skills = [
      { id: 'merchant', name: 'Market charm', desc: 'Earn more when you sell', icon: '◉', detail: 'Sell bonus', percent: level => `${level * 10}%` },
      { id: 'greenThumb', name: 'Green thumb', desc: 'Help every seed grow faster', icon: '♧', detail: 'Grow time', percent: level => `${Math.round((1 - Math.pow(.91, level)) * 100)}% faster` },
      { id: 'luckyPatch', name: 'Lucky patch', desc: 'Meet more marvelous mutations', icon: '✧', detail: 'Mutation chance', percent: level => `${12 + level * 5}%` },
      { id: 'compost', name: 'Compost heap', desc: 'Cheaper seeds, same harvest', icon: '❉', detail: 'Seed price', percent: level => `-${level * 5}%` },
      { id: 'plotSurvey', name: 'Plot survey', desc: 'Dig new patches for less', icon: '⌗', detail: 'Patch price', percent: level => `-${level * 7}%` },
      { id: 'bigBasket', name: 'Big basket', desc: 'Store more before selling', icon: '▤', detail: 'Pantry space', percent: level => `+${level * 12} slots` }
    ];
    ui.panel.innerHTML = `<div class="panel-title-row"><div><h2>Little talents</h2><div class="panel-kicker">Good things grow when you do</div></div><span class="quiet-icon">✧</span></div>
      ${skills.map(skill => { const level = state.skills[skill.id] || 0; const cost = skillCost(skill.id, level); const maxed = level >= SKILL_MAX[skill.id]; const current = skill.percent(level); const next = skill.percent(level + 1); return `<div class="skill-card"><div class="skill-card-top"><span class="skill-icon">${skill.icon}</span><span class="skill-description"><strong>${skill.name}</strong><small>${skill.desc}</small></span><span class="skill-level">${level} / ${SKILL_MAX[skill.id]}</span></div><div class="skill-card-bottom"><span class="skill-effect">${skill.detail}: <strong>${current}</strong> → ${next}</span>${maxed ? '<span class="badge">MASTERED</span>' : `<button class="skill-button" data-skill="${skill.id}" ${farmConnected && !state.pendingRubyAction && hasFunds(cost) ? '' : 'disabled'}>Learn · <span class="cost-icon">${currencyIcon(cost.type)}</span> ${cost.amount}</button>`}</div></div>`; }).join('')}
      <div class="callout"><span class="callout-icon">◉</span><p>You can sell for up to <strong>${goldCapToday().toLocaleString()} gold</strong> a day at ${state.unlocked} patches, rising to <strong>${DAILY_GOLD_CAP.toLocaleString()}</strong> once all 50 are open. Long grow times and patch costs keep the 10M gold mark at roughly a month.</p></div>`;
  }

  function plotPrice() {
    const base = Math.max(60, Math.floor(200 * Math.pow(Math.max(1, state.unlocked - 7), 1.9) / 10) * 10);
    return Math.max(60, Math.floor(base * (1 - (state.skills.plotSurvey || 0) * 0.07)));
  }
  function seedPrice(key) {
    const crop = CROPS[key];
    if (!crop || !crop.seedCost) return crop ? crop.seedCost : 0;
    return Math.max(1, Math.floor(crop.seedCost * (1 - (state.skills.compost || 0) * 0.05)));
  }

  function plant(index) {
    if (index >= state.unlocked) { showToast(index < PLOT_LIMIT ? `That patch is still asleep. Unlock it for ${plotPrice()} gold.` : 'That patch is beyond your farm.'); return; }
    if (state.plots[index]?.crop) { selectedPlot = index; const stage = stageFor(state.plots[index]); if (stage === 'ready') harvest(index); else { showToast(`${cropFor(state.plots[index]).name} is growing. A little patience!`); render(); } return; }
    const kind = state.selectedSeed;
    if (!(state.seeds[kind] > 0)) { activeTab = 'shop'; render(); showToast('No seeds left in your pouch. Pick some up at the market!'); return; }
    if (farmConnected && !state.pendingRubyAction) beginFarmAction('PLANT', { CROP: kind, PLOT: String(index) });
  }

  function harvest(index) {
    const plot = state.plots[index];
    if (!plot?.crop || stageFor(plot) !== 'ready') return false;
    if (availableCapacity() < 1) { activeTab = 'storage'; render(); showToast('Your pantry is full. Sell or expand it to gather more!'); return false; }
    if (farmConnected && !state.pendingRubyAction) beginFarmAction('HARVEST', { PLOT: String(index) });
    return true;
  }
  function mutationEmoji(key) { return CROPS[key]?.mutationEmoji || '✨'; }

  function harvestAll() {
    if (!readyCount()) { showToast('Nothing ripe just yet. Give your little sprouts a moment.'); return; }
    if (farmConnected && !state.pendingRubyAction) beginFarmAction('HARVEST_ALL');
  }

  function totalProduceValue() { return Object.values(state.produce).reduce((total, item) => total + (item?.count || 0) * item.value, 0); }
  function sellItem(key) {
    const item = state.produce[key]; if (!item?.count) return;
    if (farmConnected && !state.pendingRubyAction) beginFarmAction('SELL', { KEY: key });
  }
  function sellAll() { if (!itemCount()) return; if (farmConnected && !state.pendingRubyAction) beginFarmAction('SELL_ALL'); }

  function buySeed(key) {
    const crop = CROPS[key]; if (!crop || !farmConnected || state.pendingRubyAction) return;
    if (crop.seedRubyCost ? walletRuby < crop.seedRubyCost : state.gold < seedPrice(key)) return;
    beginFarmAction('BUY_SEED', { CROP: key });
  }
  function makeRubyActionId() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, '');
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  }
  async function postRubyWallet(fields) {
    const response = await fetch('../wallet/moss_moon.php', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
      body: new URLSearchParams(fields).toString()
    });
    return response.json();
  }
  async function loadRubyWallet() {
    try {
      const response = await postRubyWallet({ ACTION: 'INFO', LUCKY_PATCH_LEVEL: String(state.skills.luckyPatch || 0) });
      if (response.STATE !== 'SUCCESS') throw new Error(response.msg || 'wallet unavailable');
      walletRuby = Math.max(0, Number(response.wallet) || 0);
      rubyWalletConnected = true;
      accountId = String(response.account_id || '');
      serverModeActive = true;
      localFarmBackupReady = preserveLocalFarmBackup();
      if (state.pendingRubyAction && !state.pendingRubyAction.accountId) {
        state.pendingRubyAction = null;
        saveState();
        showToast('An older unlinked purchase was canceled. Check the account mailbox before retrying.');
      }
      state.accountId = accountId;
      syncServerFarm(response.farm);
      farmConnected = localFarmBackupReady;
      characterCatalog = Array.isArray(response.characters) ? response.characters : [];
      characterPrices = response.character_prices || {};
      render();
      await submitPendingRubyAction();
    } catch {
      walletRuby = null;
      rubyWalletConnected = false;
      farmConnected = false;
      accountId = '';
      render();
    }
  }
  async function submitPendingRubyAction() {
    const pending = state.pendingRubyAction;
    if (!pending || rubyActionInFlight) return;
    if (!pending.accountId || pending.accountId !== accountId) {
      showToast('A purchase is pending for another account. Sign in to that account to finish it.');
      return;
    }
    rubyActionInFlight = true;
    try {
      const response = await postRubyWallet({
        ACTION: pending.action,
        ACTION_ID: pending.id,
        ...(pending.level ? { LEVEL: String(pending.level) } : {}),
        ...(pending.fields || {})
      });
      if (response.STATE !== 'SUCCESS') {
        if (response.CODE === 'AUTH_REQUIRED' || response.CODE === 'AUTH_EXPIRED') {
          walletRuby = null;
          rubyWalletConnected = false;
          farmConnected = false;
          accountId = '';
          render();
          showToast('Sign in again to finish this pending purchase.');
          return;
        }
        if (response.wallet !== undefined) walletRuby = Math.max(0, Number(response.wallet) || 0);
        state.pendingRubyAction = null;
        saveState();
        render();
        const message = response.msg === 'not enough ruby' ? 'Not enough shared RubyFarm ruby.'
          : response.msg === 'not enough farm gold' ? 'Not enough farm Gold.'
          : response.msg === 'character already owned' ? 'You already own this character.'
          : response.msg || 'Purchase could not be completed.';
        showToast(message);
        const characterMessage = document.getElementById('character-shop-message');
        if (characterMessage && pending.action === 'BUY_CHARACTER') characterMessage.textContent = message;
        return;
      }
      walletRuby = Math.max(0, Number(response.wallet) || 0);
      rubyWalletConnected = true;
      syncServerFarm(response.farm);
      farmConnected = true;
      state.pendingRubyAction = null;
      saveState();
      render();
      const message = response.action === 'character'
        ? `${response.character_name} (${response.star}★) sent to your account mailbox.`
        : response.action === 'care_package' ? 'Care package added to your seed pouch.'
        : response.action === 'lucky_patch' ? 'Lucky Patch leveled up!'
        : response.action === 'buy_seed' ? 'Seed added to your pouch.'
        : response.action === 'plant' ? 'Seed planted.'
        : response.action === 'harvest' ? 'Harvest added to storage.'
        : response.action === 'sell' ? `Harvest sold${Number(response.earned_gold) ? ` for ${formatNumber(response.earned_gold)} Gold` : ''}${Number(response.earned_ruby) ? `, ${formatNumber(response.earned_ruby)} Ruby` : ''}${Number(response.earned_diamond) ? `, ${formatNumber(response.earned_diamond)} Diamond` : ''}.`
        : response.action === 'reset_farm' ? 'Farm progress reset.'
        : 'Farm updated.';
      showToast(message);
      const characterMessage = document.getElementById('character-shop-message');
      if (characterMessage && response.action === 'character') characterMessage.textContent = message;
    } catch {
      walletRuby = null;
      rubyWalletConnected = false;
      farmConnected = false;
      accountId = '';
      render();
      showToast('Wallet connection lost. This purchase will retry when connected.');
    } finally {
      rubyActionInFlight = false;
    }
  }
  function beginRubyAction(action, fields = {}) {
    if (!rubyWalletConnected || walletRuby === null || !farmConnected) { showToast('Sign in through RubyFarm to use the account farm and shared Ruby wallet.'); return; }
    if (state.pendingRubyAction) { showToast('A Ruby purchase is waiting to finish.'); return; }
    if (!accountId) { showToast('Account identity is not ready. Reload after signing in.'); return; }
    state.pendingRubyAction = { id: makeRubyActionId(), action, fields, accountId };
    if (!saveState()) { state.pendingRubyAction = null; return; }
    submitPendingRubyAction();
  }
  function beginFarmAction(action, fields = {}) { beginRubyAction(action, fields); }
  function buyCarePackage() {
    if (walletRuby < 3 || state.pendingRubyAction) return;
    beginRubyAction('BUY_CARE_PACKAGE');
  }
  function buyCharacter() {
    const characterId = Number(selectedCharacterId);
    if (!Number.isInteger(characterId) || characterId <= 0) return;
    const character = characterCatalog.find(entry => entry.id === characterId);
    if (!character) return;
    const confirmed = window.confirm(`Buy ${character.name} (${character.star}★) and send it to your account mailbox?`);
    if (!confirmed) return;
    beginFarmAction('BUY_CHARACTER', { CHARACTER_ID: String(characterId) });
  }
  function unlockPlot() {
    if (state.unlocked >= PLOT_LIMIT) { showToast('Your farm has all 50 lovely patches!'); return; }
    const price = plotPrice(); if (state.gold < price) { showToast(`That patch costs ${price} gold. Sell a few goodies first!`); return; }
    if (farmConnected && !state.pendingRubyAction) beginFarmAction('UNLOCK_PLOT');
  }
  function upgradeStorage(type) {
    if (state.capacity >= 100) return;
    if ((type === 'gold' && state.gold < 240) || (type === 'diamond' && state.diamond < 2)) { showToast(type === 'gold' ? 'You need 240 gold to expand the pantry.' : 'You need 2 diamonds to build the bigger shed.'); return; }
    if (farmConnected && !state.pendingRubyAction) beginFarmAction('UPGRADE_STORAGE', { TYPE: type });
  }
  function buySkill(key) {
    const level = state.skills[key]; if (level >= 5) return;
    const cost = skillCost(key, level); if (!hasFunds(cost)) { showToast(`Not quite enough ${cost.type} for that skill yet.`); return; }
    if (cost.type === 'ruby') { beginFarmAction('BUY_LUCKY_PATCH', { LEVEL: String(level + 1) }); return; }
    if (farmConnected && !state.pendingRubyAction) beginFarmAction('BUY_SKILL', { KEY: key });
  }

  function routeTab(tab) { if (!['farm', 'storage', 'shop', 'skills'].includes(tab)) return; activeTab = tab; render(); }
  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect(); if (!rect.width || !rect.height) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(rect.width * dpr); canvas.height = Math.floor(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); drawFarm();
  }

  function drawFarm() {
    const width = canvas.clientWidth; const height = canvas.clientHeight; if (!width || !height) return;
    ctx.clearRect(0, 0, width, height);
    drawScenery(width, height);
    const tileW = Math.min(width / 10.5, height / 7.5);
    const tileH = tileW * .49;
    const originX = width / 2;
    const originY = Math.max(75, height * .30);
    const now = Date.now();
    const tiles = [];
    for (let row = 0; row < 5; row += 1) for (let column = 0; column < 10; column += 1) {
      const x = originX + (column - row) * tileW * .5;
      const y = originY + (row + column) * tileH * .5;
      tiles.push({ row, column, index: row * 10 + column, x, y });
    }
    tiles.sort((a, b) => a.row + a.column - b.row - b.column || a.row - b.row);
    for (const tile of tiles) drawPlot(tile, tileW, tileH, now);
    drawFence(width, height);
  }

  function drawScenery(width, height) {
    const ground = ctx.createLinearGradient(0, height * .40, 0, height);
    ground.addColorStop(0, '#aecb86'); ground.addColorStop(1, '#8eae6d'); ctx.fillStyle = ground; ctx.fillRect(0, height * .40, width, height * .60);
    // Layered hills and the creek make a small, legible world behind the farm.
    ctx.fillStyle = '#99bc83'; ctx.beginPath(); ctx.moveTo(0, height * .43); ctx.quadraticCurveTo(width * .19, height * .20, width * .39, height * .42); ctx.quadraticCurveTo(width * .66, height * .18, width, height * .40); ctx.lineTo(width, height * .57); ctx.lineTo(0, height * .59); ctx.fill();
    ctx.fillStyle = '#80a969'; ctx.beginPath(); ctx.moveTo(0, height * .53); ctx.quadraticCurveTo(width * .25, height * .37, width * .48, height * .54); ctx.quadraticCurveTo(width * .77, height * .34, width, height * .49); ctx.lineTo(width, height * .69); ctx.lineTo(0, height * .7); ctx.fill();
    ctx.fillStyle = '#b4d5d2'; ctx.beginPath(); ctx.moveTo(width * .69, height); ctx.bezierCurveTo(width * .64, height * .82, width * .79, height * .76, width * .73, height * .62); ctx.lineTo(width * .80, height * .63); ctx.bezierCurveTo(width * .88, height * .81, width * .74, height * .85, width * .82, height); ctx.fill();
    ctx.strokeStyle = '#daebe0'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(width * .75, height * .95); ctx.quadraticCurveTo(width * .70, height * .83, width * .78, height * .70); ctx.stroke();
    for (let i = 0; i < 8; i += 1) { const x = width * (.07 + ((i * 37) % 89) / 100); const y = height * (.48 + ((i * 19) % 35) / 100); drawFlower(x, y, i % 2 ? '#f6eab0' : '#fff3d0', .7 + (i % 3) * .15); }
    drawTree(width * .12, height * .49, .84); drawTree(width * .88, height * .45, .71);
  }
  function drawFlower(x, y, color, scale) {
    ctx.fillStyle = '#617e50'; ctx.fillRect(x - 1, y, 2, 9 * scale);
    ctx.fillStyle = color; for (let i = 0; i < 5; i += 1) { const angle = i * Math.PI * .4; ctx.beginPath(); ctx.ellipse(x + Math.cos(angle) * 3.5 * scale, y + Math.sin(angle) * 3.5 * scale, 2.3 * scale, 1.5 * scale, angle, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = '#e0ba55'; ctx.beginPath(); ctx.arc(x, y, 1.4 * scale, 0, Math.PI * 2); ctx.fill();
  }
  function drawTree(x, y, scale) {
    ctx.fillStyle = '#67894e'; ctx.beginPath(); ctx.ellipse(x, y + 20 * scale, 21 * scale, 7 * scale, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#94734f'; ctx.fillRect(x - 3 * scale, y - 2 * scale, 6 * scale, 24 * scale);
    ctx.fillStyle = '#567b51'; ctx.beginPath(); ctx.arc(x, y - 9 * scale, 16 * scale, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#739956'; ctx.beginPath(); ctx.arc(x - 9 * scale, y - 8 * scale, 10 * scale, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#8aa966'; ctx.beginPath(); ctx.arc(x + 5 * scale, y - 15 * scale, 8 * scale, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#c1d58f'; ctx.beginPath(); ctx.arc(x - 4 * scale, y - 17 * scale, 2 * scale, 0, Math.PI * 2); ctx.fill();
  }

  function drawPlot(tile, tileW, tileH, now) {
    const { x, y, index, row, column } = tile;
    const top = index < state.unlocked;
    const plot = top ? plotAt(index) : null;
    const stage = top ? stageFor(plot, now) : 'locked';
    const selected = selectedPlot === index;
    ctx.save();
    ctx.globalAlpha = top ? 1 : .65;
    ctx.fillStyle = '#6b8056'; ctx.beginPath(); ctx.ellipse(x, y + tileH * .66, tileW * .48, tileH * .24, 0, 0, Math.PI * 2); ctx.fill();
    const depth = Math.max(5, tileH * .19);
    ctx.fillStyle = top ? '#a07752' : '#a7a893'; diamondPath(x, y, tileW * .48, tileH * .48); ctx.fill();
    ctx.fillStyle = top ? '#815c42' : '#929584'; ctx.beginPath(); ctx.moveTo(x - tileW * .48, y); ctx.lineTo(x, y + tileH * .48); ctx.lineTo(x, y + tileH * .48 + depth); ctx.lineTo(x - tileW * .48, y + depth); ctx.closePath(); ctx.fill();
    ctx.fillStyle = top ? '#966e4b' : '#9b9e8b'; ctx.beginPath(); ctx.moveTo(x + tileW * .48, y); ctx.lineTo(x, y + tileH * .48); ctx.lineTo(x, y + tileH * .48 + depth); ctx.lineTo(x + tileW * .48, y + depth); ctx.closePath(); ctx.fill();
    if (top) {
      const soil = ctx.createLinearGradient(x, y - tileH * .5, x, y + tileH * .5);
      soil.addColorStop(0, plot?.crop ? '#986d49' : '#b38b5c'); soil.addColorStop(1, plot?.crop ? '#845e41' : '#a47b51'); ctx.fillStyle = soil;
      diamondPath(x, y, tileW * .48, tileH * .48); ctx.fill();
      ctx.strokeStyle = selected ? '#fff4b4' : '#c6a47a'; ctx.lineWidth = selected ? 2 : 1; ctx.stroke();
      if (stage === 'empty') drawSoilFurrows(x, y, tileW, tileH);
      if (plot?.crop && stage !== 'ready') drawPlant(x, y - tileH * .10, cropFor(plot), stage, now, index);
      if (stage === 'ready') drawReadyCrop(x, y - tileH * .12, cropFor(plot), now, index);
      if (selected && plot?.crop && stage !== 'ready') drawGrowthArc(x, y - tileH * .10, plot, now);
      if (!plot?.crop) { ctx.fillStyle = '#f2e7c566'; ctx.font = `${Math.max(10, tileW * .16)}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText('+', x, y + 4); }
    } else {
      ctx.fillStyle = '#757b6675'; ctx.font = `bold ${Math.max(9, tileW * .13)}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText('· · ·', x, y + 3);
      if (index === state.unlocked) { ctx.fillStyle = '#e5e5d2'; ctx.font = `${Math.max(7, tileW * .10)}px sans-serif`; ctx.fillText(`${plotPrice()} ◉`, x, y + tileH * .46 + depth + 8); }
    }
    ctx.restore();
  }
  function diamondPath(x, y, rx, ry) { ctx.beginPath(); ctx.moveTo(x, y - ry); ctx.lineTo(x + rx, y); ctx.lineTo(x, y + ry); ctx.lineTo(x - rx, y); ctx.closePath(); }
  function drawSoilFurrows(x, y, tileW, tileH) {
    ctx.strokeStyle = '#88634165'; ctx.lineWidth = 1;
    for (let offset = -1; offset <= 1; offset += 1) { ctx.beginPath(); ctx.moveTo(x - tileW * .19 + offset * 3, y - tileH * .06 + offset * 2); ctx.lineTo(x + tileW * .19 + offset * 3, y + tileH * .12 + offset * 2); ctx.stroke(); }
  }
  function drawPlant(x, y, crop, stage, now, index) {
    const scale = stage === 'seedling' ? .56 : stage === 'growing' ? .79 : .99;
    const sway = Math.sin(now / 480 + index * 2) * 1.4;
    ctx.save(); ctx.translate(x + sway, y); ctx.scale(scale, scale);
    ctx.fillStyle = '#536f45'; ctx.beginPath(); ctx.ellipse(0, 12, 13, 4, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = crop.leaf; ctx.lineWidth = 2.1; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(0, 10); ctx.quadraticCurveTo(-1, -3, 0, -12); ctx.stroke();
    const leaves = [[-1, -3, -12, -9, -8], [1, 1, 12, -5, -7], [-1, 4, -13, 3, -1], [0, -4, 10, -12, -12], [0, 8, 7, 0, -2]];
    for (const [direction, sx, ex, ey, controlY] of leaves) {
      ctx.fillStyle = crop.leaf; ctx.beginPath(); ctx.moveTo(sx, ey + 3); ctx.quadraticCurveTo(sx + ex * .4, controlY - 6, sx + ex, ey); ctx.quadraticCurveTo(sx + ex * .52, ey + 5, sx, ey + 3); ctx.fill();
    }
    if (stage === 'almost') drawFruit(0, -11, crop, .7);
    ctx.restore();
  }
  function drawReadyCrop(x, y, crop, now, index) {
    const bob = Math.sin(now / 300 + index) * 2;
    drawPlant(x, y, crop, 'almost', now, index);
    ctx.save(); ctx.translate(x, y - 14 + bob); ctx.fillStyle = '#ffe89b'; ctx.globalAlpha = .8;
    for (let i = 0; i < 4; i += 1) { const angle = now / 850 + i * Math.PI / 2; ctx.beginPath(); ctx.arc(Math.cos(angle) * 14, Math.sin(angle) * 7, 1.4, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore();
  }
  function drawFruit(x, y, crop, scale) {
    ctx.fillStyle = crop.color;
    if (crop.name === 'Carrot') { ctx.beginPath(); ctx.moveTo(x - 4 * scale, y - 2 * scale); ctx.quadraticCurveTo(x + 6 * scale, y - 4 * scale, x + 4 * scale, y + 1 * scale); ctx.lineTo(x, y + 9 * scale); ctx.lineTo(x - 2 * scale, y + 1 * scale); ctx.fill(); }
    else if (crop.name === 'Tomato') { ctx.beginPath(); ctx.arc(x, y, 5 * scale, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = crop.leaf; ctx.beginPath(); ctx.moveTo(x, y - 4 * scale); ctx.lineTo(x - 4 * scale, y - 7 * scale); ctx.lineTo(x, y - 6 * scale); ctx.lineTo(x + 4 * scale, y - 7 * scale); ctx.fill(); }
    else if (crop.name === 'Strawberry') {
      ctx.beginPath(); ctx.moveTo(x, y + 6 * scale); ctx.bezierCurveTo(x - 2 * scale, y + 4 * scale, x - 7 * scale, y, x - 5 * scale, y - 3 * scale); ctx.bezierCurveTo(x - 4 * scale, y - 6 * scale, x, y - 4 * scale, x, y - 2 * scale); ctx.bezierCurveTo(x, y - 5 * scale, x + 5 * scale, y - 6 * scale, x + 6 * scale, y - 2 * scale); ctx.bezierCurveTo(x + 7 * scale, y + 1 * scale, x + 2 * scale, y + 5 * scale, x, y + 6 * scale); ctx.fill();
      ctx.fillStyle = crop.leaf; ctx.beginPath(); ctx.moveTo(x, y - 2 * scale); ctx.lineTo(x - 5 * scale, y - 5 * scale); ctx.lineTo(x - 2 * scale, y - 1 * scale); ctx.lineTo(x, y - 5 * scale); ctx.lineTo(x + 2 * scale, y - 1 * scale); ctx.lineTo(x + 5 * scale, y - 5 * scale); ctx.lineTo(x + 2 * scale, y); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#ffe6a1'; for (const [seedX, seedY] of [[-2, 0], [2, 1], [0, 4]]) { ctx.beginPath(); ctx.arc(x + seedX * scale, y + seedY * scale, .65 * scale, 0, Math.PI * 2); ctx.fill(); }
    }
    else if (crop.name === 'Pumpkin') {
      ctx.beginPath(); ctx.ellipse(x, y, 7 * scale, 5.5 * scale, 0, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(105, 61, 32, .55)'; ctx.lineWidth = scale;
      for (const offset of [-3, 0, 3]) { ctx.beginPath(); ctx.ellipse(x + offset * scale, y, 2.2 * scale, 5 * scale, 0, 0, Math.PI * 2); ctx.stroke(); }
      ctx.fillStyle = crop.leaf; ctx.fillRect(x - scale, y - 7 * scale, 2 * scale, 3 * scale);
    }
    else if (crop.name === 'Sunflower') {
      for (let petal = 0; petal < 8; petal += 1) { const angle = petal * Math.PI / 4; ctx.beginPath(); ctx.arc(x + Math.cos(angle) * 4 * scale, y + Math.sin(angle) * 4 * scale, 2.3 * scale, 0, Math.PI * 2); ctx.fill(); }
      ctx.fillStyle = '#76502d'; ctx.beginPath(); ctx.arc(x, y, 3 * scale, 0, Math.PI * 2); ctx.fill();
    }
    else if (crop.name === 'Blue Orchid' || crop.name === 'Rubyflower' || crop.name === 'Frost Lily') {
      for (let petal = 0; petal < 6; petal += 1) { const angle = petal * Math.PI / 3; ctx.beginPath(); ctx.ellipse(x + Math.cos(angle) * 4 * scale, y + Math.sin(angle) * 4 * scale, 2.4 * scale, 1.6 * scale, angle, 0, Math.PI * 2); ctx.fill(); }
      ctx.fillStyle = crop.name === 'Rubyflower' ? '#ffe39b' : '#fff3bd'; ctx.beginPath(); ctx.arc(x, y, 2 * scale, 0, Math.PI * 2); ctx.fill();
    }
    else if (crop.name === 'Golden Melon') {
      ctx.beginPath(); ctx.ellipse(x, y, 7 * scale, 5 * scale, -.25, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(103, 128, 55, .65)'; ctx.lineWidth = scale;
      for (const offset of [-3, 0, 3]) { ctx.beginPath(); ctx.ellipse(x + offset * scale, y, 1.2 * scale, 4 * scale, -.25, 0, Math.PI * 2); ctx.stroke(); }
    }
    else if (crop.name === 'Starfruit') {
      ctx.beginPath(); for (let point = 0; point < 10; point += 1) { const angle = -Math.PI / 2 + point * Math.PI / 5; const radius = (point % 2 ? 3 : 7) * scale; const px = x + Math.cos(angle) * radius; const py = y + Math.sin(angle) * radius; if (!point) ctx.moveTo(px, py); else ctx.lineTo(px, py); } ctx.closePath(); ctx.fill();
    }
    else if (crop.name === 'Diamond Bloom') {
      ctx.beginPath(); ctx.moveTo(x, y - 7 * scale); ctx.lineTo(x + 6 * scale, y - 1 * scale); ctx.lineTo(x + 3 * scale, y + 7 * scale); ctx.lineTo(x - 3 * scale, y + 7 * scale); ctx.lineTo(x - 6 * scale, y - 1 * scale); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#d9ffff'; ctx.lineWidth = scale; ctx.beginPath(); ctx.moveTo(x, y - 7 * scale); ctx.lineTo(x, y + 7 * scale); ctx.moveTo(x - 6 * scale, y - 1 * scale); ctx.lineTo(x + 6 * scale, y - 1 * scale); ctx.stroke();
    }
    else if (crop.name === 'Ember Chili') {
      ctx.beginPath(); ctx.moveTo(x - 2.5 * scale, y - 5 * scale); ctx.quadraticCurveTo(x + 4 * scale, y - 3 * scale, x, y + 8 * scale); ctx.quadraticCurveTo(x - 4 * scale, y - 3 * scale, x - 2.5 * scale, y - 5 * scale); ctx.fill();
      ctx.strokeStyle = crop.leaf; ctx.lineWidth = 1.6 * scale; ctx.beginPath(); ctx.moveTo(x - 2.5 * scale, y - 5 * scale); ctx.quadraticCurveTo(x, y - 9 * scale, x + 2 * scale, y - 8 * scale); ctx.stroke();
    }
    else if (crop.name === 'Nebula Wheat') {
      ctx.strokeStyle = crop.color; ctx.lineWidth = 1.4 * scale;
      for (const offset of [-3, 0, 3]) {
        ctx.beginPath(); ctx.moveTo(x + offset * .5 * scale, y + 8 * scale); ctx.lineTo(x + offset * scale, y - 7 * scale); ctx.stroke();
        for (let grain = 0; grain < 3; grain += 1) { ctx.beginPath(); ctx.arc(x + offset * scale, y - (2 + grain * 3) * scale, 1.1 * scale, 0, Math.PI * 2); ctx.fill(); }
      }
    }
    else { for (let i = 0; i < 3; i += 1) { ctx.beginPath(); ctx.arc(x + (i - 1) * 4 * scale, y + (i % 2) * 2 * scale, 3.3 * scale, 0, Math.PI * 2); ctx.fill(); } }
  }
  function drawGrowthArc(x, y, plot, now) {
    const crop = cropFor(plot); const progress = Math.min(1, (now - plot.plantedAt) / (crop.growMs * Math.pow(.91, state.skills.greenThumb)));
    ctx.strokeStyle = '#fff6ce'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y, 13, -Math.PI / 2, -Math.PI / 2 + progress * Math.PI * 2); ctx.stroke();
  }
  function drawFence(width, height) {
    ctx.strokeStyle = '#d7c59a'; ctx.lineWidth = 2; ctx.setLineDash([4, 5]); ctx.beginPath(); ctx.moveTo(width * .12, height * .64); ctx.lineTo(width * .27, height * .89); ctx.moveTo(width * .84, height * .67); ctx.lineTo(width * .74, height * .88); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = '#f0e5c5';
    for (const [x, y] of [[width * .12, height * .64], [width * .27, height * .89], [width * .84, height * .67], [width * .74, height * .88]]) { ctx.fillRect(x - 2, y - 3, 4, 8); ctx.beginPath(); ctx.moveTo(x - 2, y - 3); ctx.lineTo(x, y - 6); ctx.lineTo(x + 2, y - 3); ctx.fill(); }
  }

  function canvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top, width: rect.width, height: rect.height };
  }
  function plotIndexAt(event) {
    const point = canvasPoint(event); const tileW = Math.min(point.width / 10.5, point.height / 7.5); const tileH = tileW * .49;
    const originX = point.width / 2; const originY = Math.max(75, point.height * .30);
    let closest = null; let closestDistance = Infinity;
    for (let row = 0; row < 5; row += 1) for (let column = 0; column < 10; column += 1) {
      const x = originX + (column - row) * tileW * .5; const y = originY + (row + column) * tileH * .5;
      const distance = Math.abs(point.x - x) / (tileW * .48) + Math.abs(point.y - y) / (tileH * .48);
      if (distance <= 1.18 && distance < closestDistance) { closestDistance = distance; closest = row * 10 + column; }
    }
    return closest;
  }

  function showToast(message) {
    const region = document.getElementById('toast-region'); const toast = document.createElement('div'); toast.className = 'toast'; toast.textContent = message; region.append(toast); window.setTimeout(() => toast.remove(), 3200);
  }
  function showModal(html) { document.getElementById('modal-content').innerHTML = html; document.getElementById('modal-backdrop').classList.remove('hidden'); }
  function closeModal() { document.getElementById('modal-backdrop').classList.add('hidden'); }
  function showGuide() {
    showModal(`<h2 id="modal-title">A little field guide</h2><p>Welcome to Fernhollow. The good things grow at their own pace.</p>
      <div class="guide-row"><span>🌱</span><span><strong>Plant:</strong> choose a seed, then tap an empty patch. Carrots are quick; moonberries are magical (and take their time).</span></div>
      <div class="guide-row"><span>⏳</span><span><strong>Grow:</strong> your crops keep growing while you're away. Come back to check on them.</span></div>
      <div class="guide-row"><span>🧺</span><span><strong>Gather & sell:</strong> tap a ripe plant or use Gather all, then sell your harvest from the pantry.</span></div>
      <div class="guide-row"><span>✧</span><span><strong>Wonder:</strong> crops might mutate into something rare and worth three times as much. Lucky Patch boosts the chance.</span></div>
      <div class="guide-row"><span>🌾</span><span><strong>Grow your farm:</strong> open new plots with gold (up to 50), expand your pantry and learn skills as you go.</span></div>`);
  }
  function askReset() {
    showModal(`<h2 id="modal-title">A fresh little start?</h2><p>This will start a brand-new farm and clear your saved progress.</p><div class="confirm-actions"><button id="cancel-reset">Keep growing</button><button class="confirm-reset" id="confirm-reset">New farm</button></div>`);
    document.getElementById('cancel-reset').addEventListener('click', closeModal);
    document.getElementById('confirm-reset').addEventListener('click', () => { closeModal(); if (farmConnected && !state.pendingRubyAction) beginFarmAction('RESET_FARM'); });
  }
  function playTone(frequency, duration) {
    if (!soundEnabled) return;
    try { audioContext ||= new AudioContext(); const oscillator = audioContext.createOscillator(); const gain = audioContext.createGain(); oscillator.type = 'sine'; oscillator.frequency.value = frequency; gain.gain.setValueAtTime(.045, audioContext.currentTime); gain.gain.exponentialRampToValueAtTime(.001, audioContext.currentTime + duration); oscillator.connect(gain); gain.connect(audioContext.destination); oscillator.start(); oscillator.stop(audioContext.currentTime + duration); } catch { /* Audio is an optional flourish. */ }
  }

  document.body.addEventListener('click', event => {
    const tab = event.target.closest('[data-tab]'); if (tab) { routeTab(tab.dataset.tab); return; }
    const openTab = event.target.closest('[data-open-tab]'); if (openTab) { routeTab(openTab.dataset.openTab); return; }
    const seed = event.target.closest('[data-seed]'); if (seed && state.seeds[seed.dataset.seed] > 0) { state.selectedSeed = seed.dataset.seed; render(); return; }
    const buy = event.target.closest('[data-buy-seed]'); if (buy) { buySeed(buy.dataset.buySeed); return; }
    const sell = event.target.closest('[data-sell]'); if (sell) { sellItem(sell.dataset.sell); return; }
    const storage = event.target.closest('[data-storage]'); if (storage) { upgradeStorage(storage.dataset.storage); return; }
    const skill = event.target.closest('[data-skill]'); if (skill) { buySkill(skill.dataset.skill); return; }
    if (event.target.closest('#buy-character-button')) { buyCharacter(); return; }
    if (event.target.closest('[data-care-package]')) { buyCarePackage(); return; }
    if (event.target.closest('#sell-all-button')) { sellAll(); return; }
    if (event.target.closest('#unlock-plot-button')) { unlockPlot(); return; }
    if (event.target.closest('#harvest-all-button')) { harvestAll(); return; }
    if (event.target.closest('#help-button')) { showGuide(); return; }
    if (event.target.closest('#reset-button')) { askReset(); return; }
    if (event.target.closest('#modal-close') || event.target.id === 'modal-backdrop') { closeModal(); return; }
    if (event.target.closest('#tip-dismiss')) { document.getElementById('world-tip').classList.add('hidden'); state.seenTip = true; saveState(); return; }
    if (event.target.closest('#zoom-button')) { document.getElementById('world-frame').classList.toggle('expanded'); resizeCanvas(); return; }
    if (event.target.closest('#sound-button')) { soundEnabled = !soundEnabled; event.target.closest('#sound-button').classList.toggle('active', soundEnabled); event.target.closest('#sound-button').title = soundEnabled ? 'Turn ambient sounds off' : 'Turn ambient sounds on'; if (soundEnabled) playTone(520, .12); return; }
  });
  canvas.addEventListener('click', event => {
    const index = plotIndexAt(event); if (index === null) return;
    const plot = plotAt(index);
    if (plot?.crop && stageFor(plot) === 'ready') harvest(index);
    else plant(index);
  });
  window.addEventListener('resize', resizeCanvas);
  window.addEventListener('online', () => { if (state.pendingRubyAction) submitPendingRubyAction(); else loadRubyWallet(); });
  window.addEventListener('keydown', event => { if (event.key === 'Escape') { closeModal(); document.getElementById('world-frame').classList.remove('expanded'); resizeCanvas(); } });
  document.addEventListener('visibilitychange', () => { if (document.hidden) saveState(); });
  window.addEventListener('beforeunload', saveState);

  function tick() {
    const now = Date.now(); const elapsedSeconds = Math.min(1, Math.max(0, (now - lastTick) / 1000));
    state.playSeconds += elapsedSeconds; lastTick = now;
    const previousDay = state.day; state.day = Math.floor(state.playSeconds / 120) + 1;
    if (state.day !== previousDay) showToast(`A new morning in Fernhollow · day ${String(state.day).padStart(2, '0')}`);
    if (now - lastSave > 15_000) { saveState(); lastSave = now; }
    syncFarmClock(); drawFarm();
    if (now - lastUiUpdate >= 1000) {
      lastUiUpdate = now;
      const ready = readyCount();
      document.getElementById('ready-count').textContent = ready;
      document.getElementById('storage-dot').classList.toggle('hidden', ready === 0);
      if (ready !== lastReadyCount) { lastReadyCount = ready; render(); }
      else if (activeTab === 'farm') renderPanel();
    }
    animationFrame = requestAnimationFrame(tick);
  }

  render(); resizeCanvas();
  if (!state.seenTip) document.getElementById('world-tip').classList.remove('hidden');
  else document.getElementById('world-tip').classList.add('hidden');
  loadRubyWallet();
  animationFrame = requestAnimationFrame(tick);
})();
