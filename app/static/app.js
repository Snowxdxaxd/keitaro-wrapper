/* Обёртка Keitaro: интерфейс без фреймворков. */

const GEOS = ["AU","US","GB","DE","FR","ES","IT","NL","PL","RO","BR","MX","CA","AT","BE","BG","CZ","DK","FI","GR","HU","IE","JP","KZ","NO","NZ","PT","SE","CH","TH","TR","UA","VN","ID","IN","MY","PH","SG","KR","RU"];

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
  return body;
}

function setResult(el, text, ok) {
  el.textContent = text;
  el.className = "result " + (ok ? "ok" : "err");
}

async function loadReference() {
  const ref = await api("/api/reference");
  $("group-name").textContent = ref.group_name;
  $("source-name").textContent = ref.source_name;

  GEOS.forEach((g) => {
    const o = document.createElement("option");
    o.value = g; o.textContent = g;
    $("geo-list").appendChild(o);
  });

  ref.offers.forEach((o) => {
    for (const id of ["offer-create", "offer-add"]) {
      const opt = document.createElement("option");
      opt.value = o.id; opt.textContent = `[${o.id}] ${o.name}`;
      $(id).appendChild(opt);
    }
  });

  ref.domains.forEach((d) => {
    const opt = document.createElement("option");
    opt.value = d.id; opt.textContent = `[${d.id}] ${d.name}`;
    $("domain").appendChild(opt);
  });
}

async function loadCampaigns() {
  const data = await api("/api/campaigns");
  const sel = $("campaign");
  sel.innerHTML = '<option value="">— выберите кампанию —</option>';
  data.items.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `[${c.id}] ${c.name}`;
    sel.appendChild(opt);
  });
}

async function loadHistory() {
  const data = await api("/api/history");
  const tbody = $("history-body");
  tbody.innerHTML = "";
  data.items.forEach((r) => {
    const tr = document.createElement("tr");
    const when = new Date(r.created_at).toLocaleString("ru-RU");
    const names = { create: "создание", add_offer: "добавление оффера", remove_offer: "удаление оффера" };
    tr.innerHTML = `<td>${when}</td><td>${names[r.action] || r.action}</td>` +
      `<td>[${r.campaign_id ?? "—"}] ${r.campaign_name}</td><td>${JSON.stringify(r.details)}</td>`;
    tbody.appendChild(tr);
  });
}

function renderFlow(flow) {
  const div = document.createElement("div");
  div.className = "flow";
  const title = document.createElement("h3");
  title.textContent = flow.name || flow.type;
  div.appendChild(title);

  if (flow.redirect_url) {
    const p = document.createElement("div");
    p.textContent = `→ редирект: ${flow.redirect_url}`;
    div.appendChild(p);
    if (flow.conditions?.length) {
      const c = document.createElement("div");
      c.className = "hint";
      const countries = flow.conditions
        .filter((x) => x.type === "country")
        .flatMap((x) => x.values || []);
      if (countries.length) c.textContent = `фильтр: страны принимать — ${countries.join(", ")}`;
      div.appendChild(c);
    }
    return div;
  }

  if (flow.offers) {
    const total = flow.offers.reduce((s, o) => s + (o.share || 0), 0);
    flow.offers.forEach((o) => {
      const row = document.createElement("div");
      row.className = "offers-row";
      const label = document.createElement("span");
      label.textContent = `[${o.offer_id}]`;
      const right = document.createElement("span");
      const pct = total ? ((o.weight / total) * 100).toFixed(2) : "0.00";
      right.innerHTML = `<span class="weight">доля ${o.share} (${pct}%)</span> ` +
        `<button class="remove" data-offer="${o.offer_id}">удалить</button>`;
      row.appendChild(label);
      row.appendChild(right);
      div.appendChild(row);
    });
    return div;
  }

  div.appendChild(document.createTextNode(JSON.stringify(flow)));
  return div;
}

async function loadCampaignDetail() {
  const id = $("campaign").value;
  const flowsEl = $("flows");
  flowsEl.innerHTML = "";
  $("add-offer-row").hidden = true;
  if (!id) return;

  const c = await api(`/api/campaigns/${id}`);
  c.flows.forEach((f) => flowsEl.appendChild(renderFlow(f)));

  const hasOffersFlow = c.flows.some((f) => f.offers);
  $("add-offer-row").hidden = !hasOffersFlow;
  if (hasOffersFlow) {
    flowsEl.querySelectorAll("button.remove").forEach((btn) => {
      btn.addEventListener("click", () => removeOffer(id, btn.dataset.offer));
    });
  }
}

async function removeOffer(campaignId, offerId) {
  try {
    await api(`/api/campaigns/${campaignId}/offers/${offerId}`, { method: "DELETE" });
    await Promise.all([loadCampaignDetail(), loadHistory()]);
  } catch (e) { alert(e.message); }
}

async function createCampaign() {
  const payload = {
    name: $("name").value.trim(),
    geo: $("geo").value.trim().toUpperCase(),
    offer_id: Number($("offer-create").value),
    domain_id: Number($("domain").value) || null,
  };
  try {
    const res = await api("/api/campaigns", { method: "POST", body: JSON.stringify(payload) });
    setResult($("create-result"), `Создано: [${res.id}] ${res.name}\n${res.url}`, true);
    await Promise.all([loadCampaigns(), loadHistory()]);
    $("campaign").value = res.id;
    await loadCampaignDetail();
  } catch (e) {
    setResult($("create-result"), e.message, false);
  }
}

async function addOffer() {
  const campaignId = $("campaign").value;
  const offerId = Number($("offer-add").value);
  try {
    await api(`/api/campaigns/${campaignId}/offers`, {
      method: "POST",
      body: JSON.stringify({ offer_id: offerId }),
    });
    await Promise.all([loadCampaignDetail(), loadHistory()]);
  } catch (e) { alert(e.message); }
}

async function checkConnection() {
  const badge = $("connection");
  try {
    await api("/api/reference");
    badge.textContent = "подключено к Keitaro";
    badge.className = "badge ok";
  } catch {
    badge.textContent = "Keitaro недоступен / нет API-ключа";
    badge.className = "badge err";
  }
}

$("btn-create").addEventListener("click", createCampaign);
$("btn-add").addEventListener("click", addOffer);
$("campaign").addEventListener("change", loadCampaignDetail);

checkConnection().then(async () => {
  try {
    await Promise.all([loadReference(), loadCampaigns(), loadHistory()]);
    await loadCampaignDetail();
  } catch (e) {
    setResult($("create-result"), "Не удалось загрузить данные: " + e.message, false);
  }
});
