const state = {
  token: sessionStorage.getItem("jirama_token"),
  user: null,
  page: "dashboard",
  charts: [],
  meters: [],
  invoices: [],
  payments: [],
  readings: [],
  notifications: [],
};
const labels = {
  dashboard: "Vue d'ensemble",
  meters: "Compteurs",
  invoices: "Factures",
  payments: "Paiements",
  consumption: "Consommation",
  notifications: "Notifications",
  profile: "Mon profil",
};
const currency = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "MGA",
  maximumFractionDigits: 0,
});
const fmtDate = (value) =>
  new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const api = async (path, options = {}) => {
  const headers = new Headers(options.headers || {});
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (response.status === 401 && state.token) {
    logout();
    throw new Error("Session expirée. Connecte-toi de nouveau.");
  }
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.detail || `Erreur ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
};
function toast(message, error = false) {
  const area = document.querySelector("#toast-area");
  area.innerHTML = `<div class="toast-message ${error ? "toast-error" : "toast-success"}">${escapeHtml(message)}</div>`;
  setTimeout(() => {
    area.innerHTML = "";
  }, 4500);
}
function showAuth(mode = "login") {
  document.querySelector("#app-shell").classList.add("d-none");
  document.querySelector("#auth-view").classList.remove("d-none");
  const register = mode === "register";
  document.querySelector("#auth-form").innerHTML =
    `<div class="eyebrow">${register ? "CRÉER UN COMPTE" : "BON RETOUR"}</div><h2>${register ? "Commencez ici." : "Ravi de vous revoir."}</h2><p>${register ? "Vos compteurs et vos factures réunis au même endroit." : "Connectez-vous pour retrouver votre suivi."}</p><form id="auth-submit-form">${register ? '<label class="form-label">Nom complet</label><input class="form-control mb-3" name="full_name" required minlength="2" autocomplete="name">' : ""}<label class="form-label">Adresse e-mail</label><input class="form-control mb-3" name="email" type="email" required autocomplete="email"><label class="form-label" for="auth-password">Mot de passe</label><div class="password-field"><input class="form-control" id="auth-password" name="password" type="password" required minlength="8" autocomplete="${register ? "new-password" : "current-password"}"><button class="password-toggle" type="button" aria-label="Afficher le mot de passe" aria-pressed="false" title="Afficher le mot de passe"><i class="fa-regular fa-eye" aria-hidden="true"></i></button></div>${register ? '<div class="form-hint">8 caractères minimum</div>' : ""}<button class="btn btn-primary auth-submit" type="submit">${register ? "Créer mon compte" : "Se connecter"} <i class="fa-solid fa-arrow-right ms-2"></i></button></form><div class="auth-switch">${register ? "Déjà inscrit ?" : "Pas encore de compte ?"} <button id="auth-toggle">${register ? "Se connecter" : "Créer un compte"}</button></div>`;
  const passwordInput = document.querySelector("#auth-password");
  const passwordToggle = document.querySelector(".password-toggle");
  passwordToggle.addEventListener("click", () => {
    const shouldShow = passwordInput.type === "password";
    passwordInput.type = shouldShow ? "text" : "password";
    passwordToggle.setAttribute("aria-pressed", String(shouldShow));
    passwordToggle.setAttribute(
      "aria-label",
      shouldShow ? "Masquer le mot de passe" : "Afficher le mot de passe",
    );
    passwordToggle.title = shouldShow
      ? "Masquer le mot de passe"
      : "Afficher le mot de passe";
    passwordToggle.innerHTML = shouldShow
      ? '<i class="fa-regular fa-eye-slash" aria-hidden="true"></i>'
      : '<i class="fa-regular fa-eye" aria-hidden="true"></i>';
  });
  document.querySelector("#auth-toggle").onclick = () =>
    showAuth(register ? "login" : "register");
  document.querySelector("#auth-submit-form").onsubmit = async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api(register ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      });
      state.token = result.access_token;
      state.user = result.user;
      sessionStorage.setItem("jirama_token", state.token);
      await startApp();
    } catch (error) {
      const node = document.createElement("div");
      node.className = "toast-message toast-error mt-3";
      node.textContent = error.message;
      event.currentTarget.append(node);
    }
  };
}
function logout() {
  state.token = null;
  state.user = null;
  sessionStorage.removeItem("jirama_token");
  showAuth();
}
async function startApp() {
  try {
    state.user = await api("/auth/me");
    document.querySelector("#auth-view").classList.add("d-none");
    document.querySelector("#app-shell").classList.remove("d-none");
    document.querySelector("#user-name").textContent = state.user.full_name;
    document.querySelector("#user-avatar").textContent = state.user.full_name
      .trim()
      .charAt(0)
      .toUpperCase();
    await navigate(location.hash.slice(1) || "dashboard");
  } catch {
    logout();
  }
}
function statusPill(status) {
  const values = {
    paid: ["Payée", "status-paid"],
    unpaid: ["À payer", "status-unpaid"],
    partial: ["Partielle", "status-partial"],
    overdue: ["En retard", "status-overdue"],
  };
  const [label, cls] = values[status] || values.unpaid;
  return `<span class="status-pill ${cls}"><i class="fa-solid fa-circle" style="font-size:5px"></i>${label}</span>`;
}
function empty(icon, title, description) {
  return `<div class="empty-state"><i class="fa-regular ${icon}"></i><h3>${title}</h3><p>${description}</p></div>`;
}
function heading(kicker, title, description, action = "") {
  if (kicker === "JEUDI · VOTRE SUIVI")
    kicker = new Intl.DateTimeFormat("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
    })
      .format(new Date())
      .toUpperCase();
  return `<div class="page-heading"><div><div class="eyebrow">${kicker}</div><h1>${title}</h1><p>${description}</p></div>${action}</div>`;
}
function button(label, type, icon = "fa-plus") {
  return `<button class="btn btn-primary" data-create="${type}"><i class="fa-solid ${icon} me-2"></i>${label}</button>`;
}
async function navigate(page) {
  if (!labels[page]) page = "dashboard";
  state.page = page;
  history.replaceState(null, "", `#${page}`);
  document
    .querySelectorAll(".side-nav a")
    .forEach((item) =>
      item.classList.toggle("active", item.dataset.page === page),
    );
  document.querySelector("#breadcrumb-label").textContent = labels[page];
  document.querySelector("#sidebar").classList.remove("open");
  await render(page);
}
async function render(page) {
  destroyCharts();
  const target = document.querySelector("#page-content");
  target.innerHTML = '<div class="panel p-4 text-secondary">Chargement…</div>';
  try {
    if (page === "dashboard") await renderDashboard(target);
    else if (page === "meters") await renderMeters(target);
    else if (page === "invoices") await renderInvoices(target);
    else if (page === "payments") await renderPayments(target);
    else if (page === "consumption") await renderConsumption(target);
    else if (page === "notifications") await renderNotifications(target);
    else if (page === "profile") renderProfile(target);
  } catch (error) {
    target.innerHTML = `<div class="panel">${empty("fa-circle-exclamation", "Impossible de charger cette page", escapeHtml(error.message))}</div>`;
  }
}
function destroyCharts() {
  state.charts.forEach((chart) => chart.destroy());
  state.charts = [];
}
function chart(canvas, config) {
  if (window.Chart)
    state.charts.push(new Chart(document.getElementById(canvas), config));
}
async function renderDashboard(target) {
  const [summary, expenses, consumptions, invoices, notifications] =
    await Promise.all([
      api("/dashboard/summary"),
      api("/dashboard/expenses"),
      api("/dashboard/consumption"),
      api("/invoices"),
      api("/notifications"),
    ]);
  state.invoices = invoices;
  state.notifications = notifications;
  updateBadges(
    summary.overdue_invoices,
    notifications.filter((n) => !n.is_read).length,
  );
  const latest = [...invoices]
    .sort((a, b) => b.issue_date.localeCompare(a.issue_date))
    .slice(0, 5);
  target.innerHTML = `${heading("JEUDI · VOTRE SUIVI", "Bonjour, " + escapeHtml(state.user.full_name.split(" ")[0]) + ".", "Voici la situation de vos factures et relevés.", button("Ajouter une facture", "invoice"))}<div class="alert-strip"><i class="fa-solid fa-circle-info"></i><span>Application indépendante : factures et paiements sont saisis manuellement. Aucun service officiel JIRAMA n’est connecté.</span></div><div class="metric-grid"><div class="metric-card"><div class="metric-top">Factures enregistrées <span class="metric-icon"><i class="fa-regular fa-file-lines"></i></span></div><div class="metric-value">${summary.total_invoices}</div><div class="metric-sub">Toutes périodes</div></div><div class="metric-card"><div class="metric-top">Total payé <span class="metric-icon green"><i class="fa-solid fa-check"></i></span></div><div class="metric-value">${currency.format(summary.total_paid)}</div><div class="metric-sub">${summary.paid_invoices} facture(s) réglée(s)</div></div><div class="metric-card"><div class="metric-top">Reste à payer <span class="metric-icon yellow"><i class="fa-solid fa-hourglass-half"></i></span></div><div class="metric-value">${currency.format(summary.total_remaining)}</div><div class="metric-sub">${summary.partial_invoices + summary.unpaid_invoices} facture(s) concernée(s)</div></div><div class="metric-card"><div class="metric-top">En retard <span class="metric-icon red"><i class="fa-solid fa-triangle-exclamation"></i></span></div><div class="metric-value">${summary.overdue_invoices}</div><div class="metric-sub">Échéance dépassée, solde dû</div></div></div><div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h2 class="panel-title">Dépenses mensuelles</h2><div class="panel-subtitle">Montants réglés · MGA</div></div></div><div class="chart-wrap"><canvas id="expense-chart" aria-label="Graphique des paiements mensuels"></canvas></div></section><section class="panel"><div class="panel-head"><div><h2 class="panel-title">Consommation</h2><div class="panel-subtitle">Historique mensuel</div></div></div><div class="chart-wrap"><canvas id="consumption-chart" aria-label="Graphique de consommation"></canvas></div></section></div><section class="panel table-panel"><div class="panel-head"><div><h2 class="panel-title">Factures récentes</h2><div class="panel-subtitle">Derniers enregistrements</div></div><button class="btn btn-light" data-go="invoices">Tout voir <i class="fa-solid fa-arrow-right ms-1"></i></button></div>${latest.length ? invoiceTable(latest, false) : empty("fa-file-lines", "Aucune facture enregistrée", "Ajoutez un compteur puis saisissez votre première facture.")}</section>`;
  chart("expense-chart", {
    type: "bar",
    data: {
      labels: expenses.map((x) => x.period),
      datasets: [
        {
          data: expenses.map((x) => Number(x.amount)),
          backgroundColor: "#3986a4",
          borderRadius: 4,
          maxBarThickness: 36,
        },
      ],
    },
    options: chartOptions("MGA"),
  });
  const periods = [...new Set(consumptions.map((x) => x.period))];
  chart("consumption-chart", {
    type: "line",
    data: {
      labels: periods,
      datasets: [
        {
          label: "Électricité · kWh",
          data: periods.map((p) =>
            Number(
              consumptions.find(
                (x) => x.period === p && x.meter_type === "electricity",
              )?.consumption || 0,
            ),
          ),
          borderColor: "#e0aa37",
          backgroundColor: "#e0aa3720",
          tension: 0.32,
        },
        {
          label: "Eau · m³",
          data: periods.map((p) =>
            Number(
              consumptions.find(
                (x) => x.period === p && x.meter_type === "water",
              )?.consumption || 0,
            ),
          ),
          borderColor: "#3986a4",
          backgroundColor: "#3986a420",
          tension: 0.32,
        },
      ],
    },
    options: chartOptions(),
  });
}
function chartOptions(suffix = "") {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (item) =>
            `${item.dataset.label || ""} ${new Intl.NumberFormat("fr-FR").format(item.raw)} ${suffix}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: "#75838d", font: { family: "DM Sans", size: 10 } },
      },
      y: {
        beginAtZero: true,
        grid: { color: "#edf1f3" },
        ticks: { color: "#75838d", font: { family: "DM Sans", size: 10 } },
      },
    },
  };
}
function invoiceTable(items, actions = true) {
  return `<div class="table-responsive"><table class="table"><thead><tr><th>Facture</th><th>Compteur</th><th>Période</th><th>Échéance</th><th>Montant</th><th>Statut</th>${actions ? "<th></th>" : ""}</tr></thead><tbody>${items.map((invoice) => `<tr><td><button class="action-button primary-cell" data-detail-invoice="${invoice.id}" title="Voir le détail">${escapeHtml(invoice.invoice_number)}</button><div class="secondary-cell">Émise le ${fmtDate(invoice.issue_date)}</div></td><td>${escapeHtml(invoice.meter_number || "—")}<div class="secondary-cell">${invoice.meter_type === "water" ? "Eau" : "Électricité"}</div></td><td>${escapeHtml(invoice.billing_period)}</td><td>${fmtDate(invoice.due_date)}</td><td><div class="primary-cell">${currency.format(invoice.amount)}</div><div class="secondary-cell">Reste ${currency.format(invoice.remaining)}</div></td><td>${statusPill(invoice.status)}</td>${actions ? `<td><div class="action-group"><button class="action-button" title="Modifier" data-edit-invoice="${invoice.id}"><i class="fa-regular fa-pen-to-square"></i></button><button class="action-button" title="Enregistrer un paiement" data-pay="${invoice.id}"><i class="fa-solid fa-coins"></i></button><button class="action-button" title="Supprimer" data-delete-invoice="${invoice.id}"><i class="fa-regular fa-trash-can"></i></button></div></td>` : ""}</tr>`).join("")}</tbody></table></div>`;
}
async function renderMeters(target) {
  const meters = await api("/meters");
  state.meters = meters;
  target.innerHTML = `${heading("VOS INSTALLATIONS", "Compteurs", "Organisez vos points de livraison eau et électricité.", button("Ajouter un compteur", "meter"))}<section class="panel table-panel">${meters.length ? `<div class="table-responsive"><table class="table"><thead><tr><th>Numéro</th><th>Énergie</th><th>Adresse</th><th>Ajouté le</th><th></th></tr></thead><tbody>${meters.map((m) => `<tr><td class="primary-cell">${escapeHtml(m.meter_number)}</td><td>${meterLabel(m.meter_type)}</td><td>${escapeHtml(m.address || "—")}</td><td>${fmtDate(m.created_at.slice(0, 10))}</td><td><div class="action-group"><button class="action-button" title="Modifier" data-edit-meter="${m.id}"><i class="fa-regular fa-pen-to-square"></i></button><button class="action-button" title="Supprimer" data-delete-meter="${m.id}"><i class="fa-regular fa-trash-can"></i></button></div></td></tr>`).join("")}</tbody></table></div>` : empty("fa-gauge-high", "Aucun compteur pour le moment", "Ajoutez votre premier compteur pour associer vos factures.")}</section>`;
}
function meterLabel(type) {
  return type === "water"
    ? '<span class="metric-icon" style="display:inline-grid;width:24px;height:24px;vertical-align:middle;margin-right:6px"><i class="fa-solid fa-droplet"></i></span>Eau · m³'
    : '<span class="metric-icon yellow" style="display:inline-grid;width:24px;height:24px;vertical-align:middle;margin-right:6px"><i class="fa-solid fa-bolt"></i></span>Électricité · kWh';
}
async function renderInvoices(target) {
  const [meters, invoices] = await Promise.all([
    api("/meters"),
    api("/invoices"),
  ]);
  state.meters = meters;
  state.invoices = invoices;
  target.innerHTML = `${heading("SUIVI DES ÉCHÉANCES", "Factures", "Enregistrez et retrouvez vos factures manuelles.", button("Nouvelle facture", "invoice"))}<div class="filter-bar"><div class="filter-search"><i class="fa-solid fa-magnifying-glass"></i><input id="invoice-search" class="filter-control" placeholder="N° de facture"></div><select id="invoice-type-filter" class="filter-control"><option value="">Tous les compteurs</option><option value="electricity">Électricité</option><option value="water">Eau</option></select><select id="invoice-status-filter" class="filter-control"><option value="">Tous les statuts</option><option value="paid">Payée</option><option value="unpaid">À payer</option><option value="partial">Partielle</option><option value="overdue">En retard</option></select><select id="invoice-year-filter" class="filter-control"><option value="">Toutes les années</option>${[
    ...new Set(invoices.map((i) => i.billing_period.slice(0, 4))),
  ]
    .sort()
    .reverse()
    .map((y) => `<option>${y}</option>`)
    .join(
      "",
    )}</select><select id="invoice-month-filter" class="filter-control"><option value="">Tous les mois</option>${Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}">${new Intl.DateTimeFormat("fr-FR", { month: "long" }).format(new Date(2026, i, 1))}</option>`).join("")}</select></div><section class="panel table-panel" id="invoice-results">${invoices.length ? invoiceTable(invoices) : empty("fa-file-lines", "Aucune facture", "Enregistrez une facture pour la voir ici.")}</section>`;
  const apply = () => filterInvoices(invoices);
  [
    "invoice-search",
    "invoice-type-filter",
    "invoice-status-filter",
    "invoice-year-filter",
    "invoice-month-filter",
  ].forEach((id) =>
    document.getElementById(id).addEventListener("input", apply),
  );
}
function filterInvoices(invoices) {
  const query = document.querySelector("#invoice-search").value.toLowerCase(),
    type = document.querySelector("#invoice-type-filter").value,
    status = document.querySelector("#invoice-status-filter").value,
    year = document.querySelector("#invoice-year-filter").value,
    month = document.querySelector("#invoice-month-filter").value;
  const rows = invoices.filter(
    (i) =>
      i.invoice_number.toLowerCase().includes(query) &&
      (!type || i.meter_type === type) &&
      (!status || i.status === status) &&
      (!year || i.billing_period.startsWith(year)) &&
      (!month || i.billing_period.endsWith(`-${month.padStart(2, "0")}`)),
  );
  document.querySelector("#invoice-results").innerHTML = rows.length
    ? invoiceTable(rows)
    : empty(
        "fa-magnifying-glass",
        "Aucun résultat",
        "Modifiez vos filtres ou votre recherche.",
      );
}
async function renderPayments(target) {
  const payments = await api("/payments");
  const invoices = await api("/invoices");
  target.innerHTML = `${heading("HISTORIQUE", "Paiements", "Suivez les règlements complets et partiels.", button("Enregistrer un paiement", "payment", "fa-coins"))}<section class="panel table-panel">${payments.length ? `<div class="table-responsive"><table class="table"><thead><tr><th>Date</th><th>Facture</th><th>Mode</th><th>Référence</th><th>Montant réglé</th></tr></thead><tbody>${payments.map((p) => `<tr><td>${fmtDate(p.payment_date)}</td><td class="primary-cell">${escapeHtml(invoices.find((i) => i.id === p.invoice_id)?.invoice_number || `#${p.invoice_id}`)}</td><td>${escapeHtml(p.payment_method)}</td><td>${escapeHtml(p.reference_number || "—")}</td><td class="primary-cell">${currency.format(p.amount_paid)}</td></tr>`).join("")}</tbody></table></div>` : empty("fa-credit-card", "Aucun paiement enregistré", "Ajoutez un règlement depuis une facture.")}</section>`;
}
async function renderConsumption(target) {
  const [readings, meters, history] = await Promise.all([
    api("/consumptions"),
    api("/meters"),
    api("/consumptions/history"),
  ]);
  state.readings = readings;
  state.meters = meters;
  target.innerHTML = `${heading("EAU & ÉLECTRICITÉ", "Consommation", "Saisissez vos index pour suivre les évolutions mensuelles.", button("Ajouter un relevé", "consumption", "fa-gauge"))}<section class="panel mb-3"><div class="panel-head"><div><h2 class="panel-title">Historique mensuel</h2><div class="panel-subtitle">Consommation calculée depuis les relevés</div></div></div><div class="chart-wrap"><canvas id="history-chart"></canvas></div></section><section class="panel table-panel">${readings.length ? `<div class="table-responsive"><table class="table"><thead><tr><th>Date du relevé</th><th>Compteur</th><th>Ancien index</th><th>Nouvel index</th><th>Consommation</th></tr></thead><tbody>${readings.map((r) => `<tr><td>${fmtDate(r.reading_date)}</td><td>${escapeHtml(r.meter_number)}<div class="secondary-cell">${r.meter_type === "water" ? "Eau" : "Électricité"}</div></td><td>${r.previous_index}</td><td>${r.current_index}</td><td class="primary-cell">${r.consumption} ${r.meter_type === "water" ? "m³" : "kWh"}</td></tr>`).join("")}</tbody></table></div>` : empty("fa-chart-column", "Aucun relevé saisi", "Ajoutez un relevé pour visualiser votre consommation.")}</section>`;
  const periods = [...new Set(history.map((x) => x.period))];
  chart("history-chart", {
    type: "line",
    data: {
      labels: periods,
      datasets: [
        {
          label: "Électricité · kWh",
          data: periods.map((p) =>
            Number(
              history.find(
                (x) => x.period === p && x.meter_type === "electricity",
              )?.consumption || 0,
            ),
          ),
          borderColor: "#e0aa37",
          tension: 0.3,
        },
        {
          label: "Eau · m³",
          data: periods.map((p) =>
            Number(
              history.find((x) => x.period === p && x.meter_type === "water")
                ?.consumption || 0,
            ),
          ),
          borderColor: "#3986a4",
          tension: 0.3,
        },
      ],
    },
    options: {
      ...chartOptions(),
      plugins: { legend: { display: true, position: "bottom" } },
    },
  });
}
async function renderNotifications(target) {
  const notifications = await api("/notifications");
  state.notifications = notifications;
  updateBadges(null, notifications.filter((n) => !n.is_read).length);
  target.innerHTML = `${heading("RESTEZ À JOUR", "Notifications", "Rappels d’échéance et activité de votre espace.")}${notifications.length ? `<div class="notice-list">${notifications.map((n) => `<article class="notice-item ${n.is_read ? "" : "unread"}"><span class="notice-icon"><i class="fa-regular fa-bell"></i></span><div><div class="notice-title">${escapeHtml(n.title)}</div><div class="notice-message">${escapeHtml(n.message)}</div></div><span class="notice-time">${new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(new Date(n.created_at))}</span>${n.is_read ? "" : `<button class="action-button" title="Marquer comme lu" data-read-notice="${n.id}"><i class="fa-solid fa-check"></i></button>`}</article>`).join("")}</div>` : `<section class="panel">${empty("fa-bell", "Tout est calme", "Les rappels de factures apparaîtront ici.")}</section>`}`;
}
function renderProfile(target) {
  target.innerHTML = `${heading("VOTRE COMPTE", "Mon profil", "Gérez les informations associées à votre espace.")}<div class="profile-grid"><section class="panel form-panel"><h2 class="panel-title mb-3">Informations personnelles</h2><form id="profile-form"><label class="form-label">Nom complet</label><input class="form-control mb-3" name="full_name" required minlength="2" value="${escapeHtml(state.user.full_name)}"><label class="form-label">Adresse e-mail</label><input class="form-control mb-3" name="email" type="email" required value="${escapeHtml(state.user.email)}"><button class="btn btn-primary mt-2">Enregistrer</button></form></section><section class="panel form-panel"><h2 class="panel-title mb-2">À propos de l’application</h2><p class="text-secondary small lh-lg">JIRAMA Invoice Manager est un outil personnel indépendant. Les factures et paiements sont enregistrés manuellement. Aucune connexion ni affiliation officielle à la JIRAMA n’est revendiquée.</p></section></div>`;
  document.querySelector("#profile-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      state.user = await api("/auth/me", {
        method: "PATCH",
        body: JSON.stringify(Object.fromEntries(new FormData(e.currentTarget))),
      });
      document.querySelector("#user-name").textContent = state.user.full_name;
      toast("Profil mis à jour.");
    } catch (error) {
      toast(error.message, true);
    }
  };
}
function updateBadges(overdue, unread) {
  if (overdue !== null) {
    const badge = document.querySelector("#overdue-badge");
    badge.textContent = overdue;
    badge.classList.toggle("d-none", !overdue);
  }
  const badge = document.querySelector("#notification-badge"),
    dot = document.querySelector("#top-notification-dot");
  badge.textContent = unread;
  badge.classList.toggle("d-none", !unread);
  dot.classList.toggle("d-none", !unread);
}
function field(label, name, type = "text", options = {}) {
  const required = options.required === false ? "" : "required";
  const min = options.min ? `min="${options.min}"` : "";
  const max = options.max ? `max="${options.max}"` : "";
  const step = options.step ? `step="${options.step}"` : "";
  const value = options.value ? `value="${escapeHtml(options.value)}"` : "";
  const full = options.full ? "field-full" : "";
  if (type === "select")
    return `<div class="${full}"><label class="form-label">${label}</label><select class="form-select" name="${name}" ${required}>${options.items}</select></div>`;
  return `<div class="${full}"><label class="form-label">${label}</label><input class="form-control" name="${name}" type="${type}" ${required} ${min} ${max} ${step} ${value}></div>`;
}
function meterOptions() {
  return state.meters
    .map(
      (m) =>
        `<option value="${m.id}">${escapeHtml(m.meter_number)} · ${m.meter_type === "water" ? "Eau" : "Électricité"}</option>`,
    )
    .join("");
}
function openForm(type, invoice = null) {
  const forms = {
    meter: {
      title: "Ajouter un compteur",
      fields: `${field("Numéro de compteur", "meter_number")}${field("Type", "meter_type", "select", { items: '<option value="electricity">Électricité</option><option value="water">Eau</option>' })}${field("Adresse", "address", "text", { required: false, full: true })}`,
      path: "/meters",
    },
    invoice: {
      title: "Enregistrer une facture",
      fields: `${field("Compteur", "meter_id", "select", { items: meterOptions() })}${field("Numéro de facture", "invoice_number")}${field("Période de facturation", "billing_period", "month")}${field("Date d’émission", "issue_date", "date")}${field("Date limite", "due_date", "date")}${field("Montant · MGA", "amount", "number", { min: "0.01", step: "0.01" })}`,
      path: "/invoices",
    },
    payment: {
      title: "Enregistrer un paiement",
      fields: `${field("Facture", "invoice_id", "select", {
        items: state.invoices
          .filter((i) => i.remaining > 0)
          .map(
            (i) =>
              `<option value="${i.id}">${escapeHtml(i.invoice_number)} · reste ${currency.format(i.remaining)}</option>`,
          )
          .join(""),
      })}${field("Montant payé · MGA", "amount_paid", "number", { min: "0.01", step: "0.01" })}${field("Date du paiement", "payment_date", "date", { value: new Date().toISOString().slice(0, 10) })}${field("Mode de paiement", "payment_method", "select", { items: "<option>Espèces</option><option>Mobile Money</option><option>Virement bancaire</option><option>Chèque</option><option>Autre</option>" })}${field("Référence", "reference_number", "text", { required: false, full: true })}`,
      path: "/payments",
    },
    consumption: {
      title: "Ajouter un relevé",
      fields: `${field("Compteur", "meter_id", "select", { items: meterOptions() })}${field("Date du relevé", "reading_date", "date")}${field("Ancien index", "previous_index", "number", { min: "0", step: "0.001" })}${field("Nouvel index", "current_index", "number", { min: "0", step: "0.001" })}`,
      path: "/consumptions",
    },
  };
  const config = forms[type];
  if (!config) return;
  if (
    (type === "invoice" && !state.meters.length) ||
    (type === "consumption" && !state.meters.length)
  ) {
    toast("Ajoute d’abord un compteur.", true);
    navigate("meters");
    return;
  }
  if (type === "payment" && !state.invoices.some((i) => i.remaining > 0)) {
    toast("Aucune facture avec un solde restant.", true);
    navigate("invoices");
    return;
  }
  document.querySelector("#modal-title").textContent = config.title;
  const form = document.querySelector("#entity-form");
  form.innerHTML = `<div class="field-grid">${config.fields}</div>${type === "invoice" ? '<div class="mt-3"><label class="form-label">Joindre le document (PDF ou image)</label><input class="form-control" type="file" name="document" accept=".pdf,.png,.jpg,.jpeg,.webp"></div>' : ""}<div class="form-actions"><button type="button" class="btn btn-light" data-bs-dismiss="modal">Annuler</button><button class="btn btn-primary">Enregistrer</button></div>`;
  bootstrap.Modal.getOrCreateInstance(
    document.querySelector("#form-modal"),
  ).show();
  form.onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const file = form.querySelector('[name="document"]')?.files[0];
    delete data.document;
    for (const key of ["meter_id", "invoice_id"])
      if (key in data) data[key] = Number(data[key]);
    for (const key of [
      "amount",
      "amount_paid",
      "previous_index",
      "current_index",
    ])
      if (key in data) data[key] = Number(data[key]);
    if (data.reference_number === "") data.reference_number = null;
    try {
      const result = await api(config.path, {
        method: "POST",
        body: JSON.stringify(data),
      });
      if (file && type === "invoice") {
        const upload = new FormData();
        upload.append("file", file);
        await api(`/invoices/${result.id}/upload`, {
          method: "POST",
          body: upload,
        });
      }
      bootstrap.Modal.getInstance(document.querySelector("#form-modal")).hide();
      toast("Enregistrement effectué.");
      await navigate(state.page);
    } catch (error) {
      toast(error.message, true);
    }
  };
}
async function deleteEntity(path, label) {
  if (!confirm(`Supprimer ${label} ? Cette action est définitive.`)) return;
  try {
    await api(path, { method: "DELETE" });
    toast("Suppression effectuée.");
    await navigate(state.page);
  } catch (error) {
    toast(error.message, true);
  }
}
async function handleClick(event) {
  const target = event.target.closest(
    "[data-page],[data-go],[data-create],[data-delete-meter],[data-delete-invoice],[data-pay],[data-read-notice],[data-edit-meter]",
  );
  if (!target) return;
  if (target.dataset.page || target.dataset.go) {
    event.preventDefault();
    navigate(target.dataset.page || target.dataset.go);
  } else if (target.dataset.create) {
    if (
      target.dataset.create === "invoice" ||
      target.dataset.create === "payment" ||
      target.dataset.create === "consumption"
    ) {
      if (!state.meters.length && target.dataset.create !== "payment")
        await api("/meters").then((items) => (state.meters = items));
      if (!state.invoices.length && target.dataset.create === "payment")
        state.invoices = await api("/invoices");
    }
    openForm(target.dataset.create);
  } else if (target.dataset.deleteMeter)
    deleteEntity(`/meters/${target.dataset.deleteMeter}`, "ce compteur");
  else if (target.dataset.deleteInvoice)
    deleteEntity(`/invoices/${target.dataset.deleteInvoice}`, "cette facture");
  else if (target.dataset.pay) {
    state.invoices = await api("/invoices");
    openForm("payment");
    setTimeout(() => {
      const select = document.querySelector('#entity-form [name="invoice_id"]');
      if (select) select.value = target.dataset.pay;
    }, 120);
  } else if (target.dataset.readNotice) {
    try {
      await api(`/notifications/${target.dataset.readNotice}/read`, {
        method: "PATCH",
      });
      await navigate("notifications");
    } catch (error) {
      toast(error.message, true);
    }
  } else if (target.dataset.editMeter) {
    const meter = state.meters.find(
      (x) => x.id === Number(target.dataset.editMeter),
    );
    openEditMeter(meter);
  }
}
function openInvoiceDetail(invoice) {
  document.querySelector("#modal-title").textContent =
    `Facture ${invoice.invoice_number}`;
  const form = document.querySelector("#entity-form");
  form.innerHTML = `<div class="notice-list"><div class="notice-item"><div><div class="notice-title">${escapeHtml(invoice.meter_number)} · ${invoice.meter_type === "water" ? "Eau" : "Électricité"}</div><div class="notice-message">Période ${escapeHtml(invoice.billing_period)} · émise le ${fmtDate(invoice.issue_date)}</div></div>${statusPill(invoice.status)}</div><div class="notice-item"><div><div class="notice-title">Montant initial</div><div class="notice-message">${currency.format(invoice.amount)}</div></div><div><div class="notice-title">Déjà payé</div><div class="notice-message">${currency.format(invoice.amount_paid)}</div></div><div><div class="notice-title">Reste dû</div><div class="notice-message">${currency.format(invoice.remaining)}</div></div></div><div class="notice-item"><div><div class="notice-title">Date limite</div><div class="notice-message">${fmtDate(invoice.due_date)}</div></div></div></div><div class="form-actions">${invoice.file_path ? `<button type="button" class="btn btn-light" data-download-invoice="${invoice.id}"><i class="fa-solid fa-download me-2"></i>Télécharger le document</button>` : ""}<button type="button" class="btn btn-light" data-bs-dismiss="modal">Fermer</button><button type="button" class="btn btn-primary" data-edit-invoice="${invoice.id}">Modifier</button></div>`;
  bootstrap.Modal.getOrCreateInstance(
    document.querySelector("#form-modal"),
  ).show();
}
function openEditInvoice(invoice) {
  document.querySelector("#modal-title").textContent = "Modifier la facture";
  const form = document.querySelector("#entity-form");
  form.innerHTML = `<div class="field-grid">${field("Compteur", "meter_id", "select", { items: state.meters.map((m) => `<option value="${m.id}" ${m.id === invoice.meter_id ? "selected" : ""}>${escapeHtml(m.meter_number)} · ${m.meter_type === "water" ? "Eau" : "Électricité"}</option>`).join("") })}${field("Numéro de facture", "invoice_number", "text", { value: invoice.invoice_number })}${field("Période", "billing_period", "month", { value: invoice.billing_period })}${field("Date d’émission", "issue_date", "date", { value: invoice.issue_date })}${field("Date limite", "due_date", "date", { value: invoice.due_date })}${field("Montant · MGA", "amount", "number", { min: "0.01", step: "0.01", value: invoice.amount })}</div><div class="mt-3"><label class="form-label">Remplacer le document (PDF ou image)</label><input class="form-control" type="file" name="document" accept=".pdf,.png,.jpg,.jpeg,.webp"></div><div class="form-actions"><button type="button" class="btn btn-light" data-bs-dismiss="modal">Annuler</button><button class="btn btn-primary">Enregistrer</button></div>`;
  bootstrap.Modal.getOrCreateInstance(
    document.querySelector("#form-modal"),
  ).show();
  form.onsubmit = async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const file = form.querySelector('[name="document"]').files[0];
    data.meter_id = Number(data.meter_id);
    data.amount = Number(data.amount);
    try {
      await api(`/invoices/${invoice.id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      });
      if (file) {
        const upload = new FormData();
        upload.append("file", file);
        await api(`/invoices/${invoice.id}/upload`, {
          method: "POST",
          body: upload,
        });
      }
      bootstrap.Modal.getInstance(document.querySelector("#form-modal")).hide();
      toast("Facture modifiée.");
      await navigate("invoices");
    } catch (error) {
      toast(error.message, true);
    }
  };
}
async function downloadInvoice(invoiceId) {
  try {
    const response = await fetch(`/api/invoices/${invoiceId}/download`, {
      headers: { Authorization: `Bearer ${state.token}` },
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || "Téléchargement impossible.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `facture-${invoiceId}`;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    toast(error.message, true);
  }
}
document.addEventListener("click", async (event) => {
  const target = event.target.closest(
    "[data-detail-invoice],[data-edit-invoice],[data-download-invoice]",
  );
  if (!target) return;
  if (target.dataset.downloadInvoice) {
    await downloadInvoice(target.dataset.downloadInvoice);
    return;
  }
  try {
    const invoice = await api(
      `/invoices/${target.dataset.detailInvoice || target.dataset.editInvoice}`,
    );
    if (target.dataset.detailInvoice) openInvoiceDetail(invoice);
    else {
      if (!state.meters.length) state.meters = await api("/meters");
      openEditInvoice(invoice);
    }
  } catch (error) {
    toast(error.message, true);
  }
});
function openEditMeter(meter) {
  document.querySelector("#modal-title").textContent = "Modifier le compteur";
  const form = document.querySelector("#entity-form");
  form.innerHTML = `<div class="field-grid">${field("Numéro de compteur", "meter_number", "text", { value: meter.meter_number })}${field("Type", "meter_type", "select", { items: `<option value="electricity" ${meter.meter_type === "electricity" ? "selected" : ""}>Électricité</option><option value="water" ${meter.meter_type === "water" ? "selected" : ""}>Eau</option>` })}${field("Adresse", "address", "text", { required: false, value: meter.address, full: true })}</div><div class="form-actions"><button type="button" class="btn btn-light" data-bs-dismiss="modal">Annuler</button><button class="btn btn-primary">Enregistrer</button></div>`;
  bootstrap.Modal.getOrCreateInstance(
    document.querySelector("#form-modal"),
  ).show();
  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(`/meters/${meter.id}`, {
        method: "PUT",
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      bootstrap.Modal.getInstance(document.querySelector("#form-modal")).hide();
      toast("Compteur modifié.");
      await navigate("meters");
    } catch (error) {
      toast(error.message, true);
    }
  };
}
document.addEventListener("click", handleClick);
document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    if (state.token) await api("/auth/logout", { method: "POST" });
  } catch {}
  logout();
});
document
  .querySelector("#menu-button")
  .addEventListener("click", () =>
    document.querySelector("#sidebar").classList.toggle("open"),
  );
window.addEventListener("hashchange", () => navigate(location.hash.slice(1)));
if (state.token) startApp();
else showAuth();
