import api from './axios'

// Reporting + recherche globale + notifications in-app (lecture seule).
const reportingApi = {
  getDashboard: () => api.get('/reporting/dashboard/'),
  // Recherche transverse : ?q=<terme> → résultats groupés par type.
  search: (q) => api.get('/reporting/search/', { params: { q } }),
  // Cloche de notifications (activités en retard, garanties, impayés).
  getNotifications: () => api.get('/reporting/notifications/'),
  // Tableau de bord valeur du pipeline (par étape, prévision, devis, pertes).
  getPipeline: () => api.get('/reporting/pipeline/'),
  // Hub Rapports (T13/T14/T15) — ventes, stock, service.
  salesReport: () => api.get('/reporting/reports/sales/'),
  stockReport: () => api.get('/reporting/reports/stock/'),
  serviceReport: () => api.get('/reporting/reports/service/'),
  reportXlsx: (kind) =>
    api.get(`/reporting/reports/${kind}/`, { params: { export: 'xlsx' }, responseType: 'blob' }),
  // Insights (N49/N70/N95/N78/N80) — lecture seule.
  recurringRevenue: () => api.get('/reporting/insights/recurring-revenue/'),
  auditLog: (params) => api.get('/reporting/insights/audit-log/', { params }),
  jobCosting: () => api.get('/reporting/insights/job-costing/'),
  analytics: () => api.get('/reporting/insights/analytics/'),
  // N99 — commissions commerciales (admin). Période optionnelle ?from=&to=.
  commissions: (params) =>
    api.get('/reporting/insights/commissions/', { params }),
  // Export xlsx d'un insight donné (recurring-revenue, audit-log, analytics).
  insightXlsx: (slug, params) =>
    api.get(`/reporting/insights/${slug}/`,
      { params: { ...(params || {}), export: 'xlsx' }, responseType: 'blob' }),
  // Export .xlsx de la balance âgée (créances par client + tranches d'âge),
  // borné à la société côté serveur.
  balanceAgeeXlsx: () =>
    api.get('/reporting/balance-agee/export/', { responseType: 'blob' }),
  // N32 — Archive documentaire (lecture seule) par client / par chantier.
  getArchiveClient: (id) => api.get(`/reporting/archive/client/${id}/`),
  getArchiveChantier: (id) => api.get(`/reporting/archive/chantier/${id}/`),
  // N84 — Calendrier / agenda. Fenêtre ?from=&to=, filtres ?assignee=&types=.
  getCalendar: (params) => api.get('/reporting/calendar/', { params }),
  rescheduleCalendar: (payload) =>
    api.post('/reporting/calendar/reschedule/', payload),
  // FG6 — URL d'abonnement ICS de l'utilisateur (Google/Outlook). Réponse
  // {token, url}. L'URL .ics est authentifiée par jeton signé (sans session).
  getCalendarSubscription: () =>
    api.get('/reporting/calendar/subscription/'),
  // N85 — Vue carte. Points géolocalisés ; filtres optionnels ?types=&statuts=.
  getGeoPoints: (params) => api.get('/reporting/geo/', { params }),
  // FG91 — Rapports sauvegardés (CRUD). company + owner posés côté serveur.
  listSavedReports: () => api.get('/reporting/saved-reports/'),
  createSavedReport: (data) => api.post('/reporting/saved-reports/', data),
  updateSavedReport: (id, data) =>
    api.patch(`/reporting/saved-reports/${id}/`, data),
  deleteSavedReport: (id) => api.delete(`/reporting/saved-reports/${id}/`),
  // FG96 — Config de tableau de bord (par utilisateur / palier de rôle).
  //   listDashboardConfigs → CRUD ; effectiveDashboardConfig → la config
  //   résolue pour l'utilisateur courant (per-user > palier > défaut Python).
  //   company forcée côté serveur.
  listDashboardConfigs: () => api.get('/reporting/dashboard-config/'),
  effectiveDashboardConfig: () =>
    api.get('/reporting/dashboard-config/effective/'),
  saveDashboardConfig: (id, data) => id
    ? api.patch(`/reporting/dashboard-config/${id}/`, data)
    : api.post('/reporting/dashboard-config/', data),
  deleteDashboardConfig: (id) =>
    api.delete(`/reporting/dashboard-config/${id}/`),
  // FG92 — Comparaison périodique (MoM/YoY). ?compare=prev|yoy.
  dashboardCompare: (compare) =>
    api.get('/reporting/dashboard/', { params: { compare } }),
  salesReportCompare: (params) =>
    api.get('/reporting/reports/sales/', { params }),
  // FG93 — Classement commerciaux.
  salesLeaderboard: (params) =>
    api.get('/reporting/insights/sales-leaderboard/', { params }),
  // FG94 — Données custom-field pour reporting (group-by, filtres ?cf_<code>=).
  cfGroupBy: (module, code, params) =>
    api.get('/reporting/insights/cf-group-by/', {
      params: { module, code, ...(params || {}) },
    }),
  // FG97 — Analytiques du Journal.
  // WIR20 — préfixe corrigé : l'endpoint est monté sous `apps.audit.urls`
  // (`/audit/analytics/`), jamais sous `/reporting/` (404 avant ce fix).
  auditAnalytics: (params) =>
    api.get('/audit/analytics/', { params }),
  // FG98 — Cohortes / saisonnalité.
  cohorts: (params) =>
    api.get('/reporting/insights/cohorts/', { params }),
  // FG99 — Rentabilité par segment (admin).
  profitability: (params) =>
    api.get('/reporting/insights/profitability/', { params }),
  // FG29 — Vélocité par étape du pipeline (durée moyenne + leads en attente
  // par étape). Distinct de `sales_velocity` (délai global lead→signature).
  funnelVelocity: () => api.get('/reporting/pipeline/velocity/'),
  // ARC40 — KPI fédérés : tuiles agrégées des providers `kpi_providers`
  // déclarés par les modules actifs (rh/paie/contrats/compta…).
  kpiFederes: () => api.get('/reporting/reports/kpi-federes/'),
  // QJ18 — Tableau de bord commercial (entonnoir, vélocité, classement).
  commercialDashboard: (params) =>
    api.get('/reporting/commercial/dashboard/', { params }),
  // QJ19 — Win/loss par canal/source + top motifs de perte.
  winLossBySource: (params) =>
    api.get('/reporting/commercial/win-loss-by-source/', { params }),
  // XKB1/ZCTR7-9 — Boîte d'approbations centralisée (5 sources : automation,
  // contrats, ged, installations, workflow), UNFILTRÉE par défaut.
  // ?source=/?categorie=, ?priorite=, ?trier=urgence|anciennete|montant.
  approbationsEnAttente: (params) =>
    api.get('/reporting/approbations-en-attente/', { params }),
  deciderApprobation: (source, id, decision, motif) =>
    api.post('/reporting/approbations-en-attente/decider/', {
      source, id, decision, motif,
    }),
  deciderApprobationsEnMasse: (items, decision, motif) =>
    api.post('/reporting/approbations-en-attente/decider-en-masse/', {
      items, decision, motif,
    }),
  // XPLT6 — CRUD des alertes de seuil sur KPI agrégés.
  listKpiAlertes: () => api.get('/reporting/kpi-alertes/'),
  createKpiAlerte: (data) => api.post('/reporting/kpi-alertes/', data),
  updateKpiAlerte: (id, data) => api.patch(`/reporting/kpi-alertes/${id}/`, data),
  deleteKpiAlerte: (id) => api.delete(`/reporting/kpi-alertes/${id}/`),
  // XPLT22 — classeur léger embarqué (mini-spreadsheet BI, données live).
  listClasseurs: () => api.get('/reporting/classeurs/'),
  getClasseur: (id) => api.get(`/reporting/classeurs/${id}/`),
  createClasseur: (data) => api.post('/reporting/classeurs/', data),
  updateClasseur: (id, data) => api.patch(`/reporting/classeurs/${id}/`, data),
  deleteClasseur: (id) => api.delete(`/reporting/classeurs/${id}/`),
  rafraichirClasseur: (id) => api.get(`/reporting/classeurs/${id}/rafraichir/`),
  evaluerFormuleClasseur: (id, formule) =>
    api.post(`/reporting/classeurs/${id}/evaluer/`, { formule }),
  // XSAV8 — conformité SLA + KPI SAV avancés.
  savSlaInsight: (params) => api.get('/reporting/insights/sav-sla/', { params }),
  // XFSM16 — analytics field service consolidés (FTF, MTTR, ponctualité…).
  fieldServiceReport: (params) => api.get('/reporting/reports/field/', { params }),
  // XFSM17 — scorecard coaching par technicien vs moyenne équipe.
  technicienScorecard: (params) =>
    api.get('/reporting/insights/technicien-scorecard/', { params }),
  // WIR22 — contrôle d'intégrité inter-documents (YSERV13) : anomalies
  // détectées AUJOURD'HUI, sans attendre la notification Beat hebdomadaire
  // ni lire les logs serveur. Réservé responsable/admin (backend).
  integriteInsight: () => api.get('/reporting/insights/integrite/'),
}

export default reportingApi
