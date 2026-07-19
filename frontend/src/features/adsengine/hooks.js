/* ============================================================================
   ENG29 — Contrat de hooks DOM `ae-*` du module Publicité (moteur ads).
   ----------------------------------------------------------------------------
   Comme les préfixes `ap-` / `att-` / `pp-*` que ciblent les specs Playwright,
   les hooks `ae-*` (« ads engine ») sont un CONTRAT STABLE entre l'UI et les
   tests e2e/a11y : ils sont posés en `data-testid` (RTL/axe) ET en `className`
   (sélecteurs Playwright) sur les éléments-clés des deux écrans à fort enjeu —
   la boîte d'approbation (écran-vaisseau-amiral) et le dashboard « un chiffre ».
   NE JAMAIS renommer un hook sans mettre à jour les specs qui en dépendent.
   Ce fichier EST la documentation (source unique, testée par a11y.test.jsx).
   Certains hooks d'item sont suffixés par l'id de l'action (ex. `ae-approve-11`,
   `ae-batch-toggle-11`, `ae-reject-11`).
   ========================================================================== */

export const AE_HOOKS = {
  // Dashboard « un chiffre » (ENG23) — chaque chiffre est cliquable → leads réels.
  dashboard: {
    root: 'ae-dashboard',
    hero: 'ae-hero', // coût par signature (le seul chiffre qui compte)
    tiles: ['ae-tile-spend', 'ae-tile-cpl', 'ae-tile-frequency'],
    alertBanner: 'ae-alert-banner', // bandeau ENG13
    drillPanel: 'ae-drill-panel', // liste des leads derrière un chiffre
    drillClose: 'ae-drill-close',
  },
  // Boîte d'approbation (ENG25) — approuver/rejeter structurés, batch partiel.
  approvals: {
    root: 'ae-approvals',
    card: 'ae-action-card',
    reason: 'ae-action-reason', // reason_fr (le « pourquoi »)
    artifactBudget: 'ae-artifact-budget', // diff avant→après
    artifactCreative: 'ae-artifact-creative', // préview du créatif réel
    approvePrefix: 'ae-approve-', // + id
    rejectPrefix: 'ae-reject-', // + id
    rejectReasonPrefix: 'ae-reject-reason-', // select structuré, jamais du chat
    rejectConfirmPrefix: 'ae-reject-confirm-', // + id
    batchTogglePrefix: 'ae-batch-toggle-', // + id
    batchBar: 'ae-batch-bar',
    batchApprove: 'ae-batch-approve',
  },

  // ── ENG46 — Écrans P7 (contrat DOM des NOUVEAUX écrans, axe sans violation
  // sur FlightPlan + Experiments) ──

  // Expérimentations (ENG39) — posteriors lisibles + DecisionLog filtrable.
  experiments: {
    root: 'ae-experiments', // className sur la page
    list: 'ae-exp-list',
    selectPrefix: 'ae-exp-select-', // + id d'expérimentation
    phases: 'ae-exp-phases',
    phase: 'ae-exp-phase',
    arms: 'ae-exp-arms',
    arm: 'ae-exp-arm',
    armBest: 'ae-exp-arm-best', // le favori du moteur
    pbestPrefix: 'ae-exp-pbest-', // + id de bras — P(meilleur)
    meanPrefix: 'ae-exp-mean-', // + id de bras — estimation ponctuelle
    bandPrefix: 'ae-exp-band-', // + id de bras — bande de crédibilité
    decisions: 'ae-exp-decisions',
    decision: 'ae-exp-decision',
    decisionFilter: 'ae-exp-decision-filter', // filtre par phase
  },

  // Plan de vol (ENG40) — écran-amiral : compose + préflight ADSENG38.
  flightplan: {
    root: 'ae-flightplan',
    compose: 'ae-fp-compose',
    nom: 'ae-fp-nom',
    template: 'ae-fp-template',
    phases: 'ae-fp-phases',
    phase: 'ae-fp-phase',
    variables: 'ae-fp-variables',
    varAdd: 'ae-fp-var-add',
    arms: 'ae-fp-arms',
    armPrefix: 'ae-fp-arm-', // + id de bras backlog
    validate: 'ae-fp-validate',
    simulate: 'ae-fp-simulate',
    valid: 'ae-fp-valid', // feu vert
    refusal: 'ae-fp-refusal', // refus + raisons
    refusalReason: 'ae-fp-refusal-reason',
    preflight: 'ae-fp-preflight', // panneau ADSENG38
    preflightVerdict: 'ae-fp-preflight-verdict',
    gate: 'ae-fp-gate', // une porte d'autonomie
    gateOk: 'ae-fp-gate-ok',
    gateKo: 'ae-fp-gate-ko',
  },

  // Backlog créatif (ENG41) — runway, diversité, approbation par LOT.
  backlog: {
    root: 'ae-backlog',
    campaign: 'ae-backlog-campaign',
    runway: 'ae-backlog-runway',
    diversity: 'ae-backlog-diversity',
    lot: 'ae-backlog-lot',
    approveLotPrefix: 'ae-backlog-approve-lot-', // + id de lot
    dropPrefix: 'ae-backlog-drop-', // + id de campagne
  },

  // Extension dashboard (ENG42) — onglets Pacing + Réconciliation.
  dashboardExt: {
    tabs: 'ae-dashboard-tabs',
    tabPrefix: 'ae-tab-', // + overview|pacing|reconciliation
    pacing: 'ae-pacing',
    pacingBurn: 'ae-pacing-burn', // cliquable → détail
    pacingDetail: 'ae-pacing-detail',
    recon: 'ae-recon',
    reconRow: 'ae-recon-row',
    reconOpenPrefix: 'ae-recon-open-', // + id
    reconDetail: 'ae-recon-detail',
  },

  // Règles & anomalies (ENG43) — picker + dry-run + anomalies.
  rules: {
    root: 'ae-rules',
    catalogue: 'ae-rules-catalogue',
    template: 'ae-rule-template',
    dryRunPrefix: 'ae-rule-dryrun-', // + key de gabarit
    dryRunResultPrefix: 'ae-rule-dryrun-result-', // + key
    anomaly: 'ae-anomaly',
    anomalySeverity: 'ae-anomaly-severity',
    alertHistory: 'ae-alert-history',
  },

  // Visionneuse de simulation (ENG44) — rejeu d'un run ADSENG36.
  simulation: {
    root: 'ae-simulation',
    runPrefix: 'ae-sim-run-', // + id de run
    report: 'ae-sim-report',
    scenario: 'ae-sim-scenario',
    verdict: 'ae-sim-verdict',
    allocations: 'ae-sim-allocations',
    step: 'ae-sim-step',
    armBudget: 'ae-sim-arm-budget',
    decision: 'ae-sim-decision',
  },

  // Reporting (ENG45) — drill-downs + export CSV.
  reports: {
    root: 'ae-reports',
    variantsTable: 'ae-reports-variants-table',
    variantRow: 'ae-reports-variant-row',
    funnelStep: 'ae-reports-funnel-step',
    cohortRow: 'ae-reports-cohort-row',
    export: 'ae-reports-export', // lien de téléchargement CSV
  },

  // PUB40 — Sélecteur de période + comparaison (`DateRangeBar`, partagé par
  // Dashboard/Cockpit/Campagnes/Journal).
  dateRange: {
    root: 'ae-daterange',
    presetPrefix: 'ae-daterange-preset-', // + hier|7j|30j|personnalise
    debut: 'ae-daterange-debut', // saisie personnalisée
    fin: 'ae-daterange-fin',
    compare: 'ae-daterange-compare', // case « comparer à la période précédente »
    summary: 'ae-daterange-summary',
  },

  // PUB41 — Fraîcheur + panne visibles (`SyncStatusBanner`, montée sur
  // Dashboard/Cockpit/Campagnes/Journal/Approbations/Commentaires) + état-
  // erreur distinct de l'état-vide sur chaque écran qui l'affiche.
  syncStatus: {
    banner: 'ae-sync-banner', // bandeau global « Meta ne répond plus… »
    // Suffixe par écran : `-cockpit`/`-camp`/`-log`/`-approvals`/`-comments`.
    loadErrorPrefix: 'ae-', // + '<écran>-load-error' (ex. ae-cockpit-load-error)
    refreshApprovals: 'ae-approvals-refresh', // reprise manuelle du sondage
    refreshComments: 'ae-comments-refresh',
  },

  // PUB43 — Vues enregistrées un-clic du Cockpit (Top Ads/En fatigue/En
  // baisse/Meilleures vidéos), filtre+tri figés + mémoire localStorage.
  cockpitViews: {
    group: 'ae-cockpit-views',
    tabPrefix: 'ae-cockpit-view-', // + toutes|top|fatigue|baisse|videos
  },

  // PUB42 — File « Aujourd'hui » unifiée (écran d'accueil `/publicite`).
  today: {
    root: 'ae-today',
    list: 'ae-today-list',
    item: 'ae-today-item', // <Link>, cliquable vers l'écran de l'item
    itemBadge: 'ae-today-item-badge', // catégorie (garde_fou/alerte/…)
    empty: 'ae-today-empty',
    loadError: 'ae-today-load-error',
    navBadge: 'ae-nav-today-badge', // pastille de comptage sur l'icône de nav
  },
}

export default AE_HOOKS
