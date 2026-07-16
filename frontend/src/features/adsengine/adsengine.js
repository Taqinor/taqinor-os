/* ============================================================================
   ADSENGINE — logique métier PURE du module « Publicité » (sans JSX, testable).
   ----------------------------------------------------------------------------
   Helpers de présentation partagés par les écrans ENG22–ENG28 : formatage des
   montants en MAD, libellés FR déterministes, tri/ranking, mappage des cartes
   de brief vers la boîte d'approbation. Aucune valeur métier n'est INVENTÉE ici
   — ces fonctions ne font que FORMATER les nombres que l'API fournit.
   Chaque tâche ENGxx ajoute ses helpers dédiés dans ce fichier (un commit par
   tâche), les écrans restent fins.
   ========================================================================== */

// ── Formatage numérique (séparateur de milliers FR, espace) ──
// Retourne un tiret cadratin « — » pour toute valeur non finie (jamais « 0 »
// ni « NaN » à l'écran quand la donnée manque).
export function formatNumber(value, decimals = 0) {
  const n = typeof value === 'string' ? Number(value) : value
  if (n === null || n === undefined || !Number.isFinite(n)) return '—'
  const fixed = Math.abs(decimals) > 0 ? n.toFixed(decimals) : String(Math.round(n))
  const [intPart, decPart] = fixed.split('.')
  const sign = intPart.startsWith('-') ? '-' : ''
  const digits = sign ? intPart.slice(1) : intPart
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  return decPart ? `${sign}${grouped},${decPart}` : `${sign}${grouped}`
}

// Montant en dirhams : « 1 234 MAD » (ou « — » si la donnée manque).
export function formatMAD(value, decimals = 0) {
  const formatted = formatNumber(value, decimals)
  return formatted === '—' ? '—' : `${formatted} MAD`
}

// Ratio/nombre décimal simple (ex. fréquence « 1,8 ») — « — » si absent.
export function formatRatio(value, decimals = 1) {
  return formatNumber(value, decimals)
}

// ── ENG22 — Statuts de câblage (ENG12 health) ──
// Normalise la réponse de santé (tableau `statuses` OU objet plat clé→bool)
// en une liste stable [{ key, label, ok, detail }]. Une valeur booléenne vraie
// = câblé/OK ; un objet { ok, detail } conserve le détail. Repli : [].
const WIRING_LABELS = {
  token: "Jeton d'accès (System User)",
  access_token: "Jeton d'accès (System User)",
  ad_account: 'Compte publicitaire',
  ad_account_id: 'Compte publicitaire',
  pixel: 'Pixel',
  capi: 'API de conversions (CAPI)',
  page: 'Page Facebook',
  paused: 'Client en pause (par design)',
  business: 'Business Portfolio',
}

export function normalizeWiringStatuses(raw) {
  if (!raw) return []
  const list = Array.isArray(raw) ? raw : (raw.statuses || null)
  if (Array.isArray(list)) {
    return list
      .filter(Boolean)
      .map(s => ({
        key: s.key,
        label: s.label || WIRING_LABELS[s.key] || s.key,
        ok: !!s.ok,
        detail: s.detail || '',
      }))
  }
  // Objet plat clé→bool | { ok, detail }.
  if (typeof raw === 'object') {
    return Object.entries(raw).map(([key, val]) => {
      const isObj = val && typeof val === 'object'
      return {
        key,
        label: WIRING_LABELS[key] || key,
        ok: isObj ? !!val.ok : !!val,
        detail: isObj ? (val.detail || '') : '',
      }
    })
  }
  return []
}

// ── ENG13/ENG23 — Alertes (bandeau dashboard) ──
// Niveaux → ton d'affichage (couleur de badge). Défaut : info.
const ALERT_TONES = {
  critique: { bg: '#fee2e2', color: '#991b1b', label: 'Critique' },
  alerte: { bg: '#ffedd5', color: '#9a3412', label: 'Alerte' },
  info: { bg: '#e0f2fe', color: '#075985', label: 'Info' },
}
export function alertTone(niveau) {
  return ALERT_TONES[niveau] || ALERT_TONES.info
}

export function normalizeAlerts(raw) {
  if (!raw) return []
  const list = Array.isArray(raw) ? raw : (raw.alerts || raw.results || [])
  return list.filter(Boolean)
}

// ── ENG24 — Classement des créatifs (réponses WhatsApp / coût par asset) ──
// Doctrine (scope P3/P7) : on classe par VALEUR business — réponses WhatsApp
// par dirham dépensé, PAS par CTR abstrait. Meilleur = coût par réponse le plus
// bas ; les créatifs sans réponse WhatsApp sont relégués en fin de classement
// (départagés par volume de réponses). Retourne une COPIE triée, chaque entrée
// enrichie de `_reponses`, `_cout`, `_coutParReponse` (null si 0 réponse).
export function rankCreatives(list) {
  return (list || [])
    .filter(Boolean)
    .map(c => {
      const reponses = Number(c.reponses_whatsapp ?? c.whatsapp_replies ?? 0) || 0
      const cout = Number(c.cout_mad ?? c.cost_mad ?? c.cout ?? 0) || 0
      const coutParReponse = reponses > 0 ? cout / reponses : null
      return { ...c, _reponses: reponses, _cout: cout, _coutParReponse: coutParReponse }
    })
    .sort((a, b) => {
      if (a._coutParReponse == null && b._coutParReponse == null) {
        return b._reponses - a._reponses
      }
      if (a._coutParReponse == null) return 1
      if (b._coutParReponse == null) return -1
      return a._coutParReponse - b._coutParReponse
    })
}

// ── ENG25 — Boîte d'approbation (EngineAction) ──
// Libellés FR déterministes des types d'action (jamais un type brut à l'écran).
export const ACTION_TYPE_LABELS = {
  create_campaign: 'Création de campagne',
  update_campaign: 'Modification de campagne',
  pause_campaign: 'Mise en pause de campagne',
  adjust_budget: 'Ajustement de budget',
  create_ad: "Création d'annonce",
  create_creative: 'Nouveau créatif',
  swap_creative: 'Rotation de créatif',
  enable_cbo: 'Activation du budget de campagne (CBO)',
  pause_for_month: "Mise en pause jusqu'à la fin du mois",
}
export function actionTypeLabel(type) {
  return ACTION_TYPE_LABELS[type] || type || 'Action'
}

function numOrNull(v) {
  const n = typeof v === 'string' ? Number(v) : v
  return Number.isFinite(n) ? n : null
}

// Diff budget avant→après d'une EngineAction (depuis les champs plats ou le
// payload). Retourne null s'il n'y a pas de diff budgétaire à montrer.
export function budgetDiff(action) {
  if (!action) return null
  const p = action.payload || {}
  const avant = numOrNull(action.budget_avant ?? p.budget_avant ?? p.budget_mad_avant)
  const apres = numOrNull(action.budget_apres ?? p.budget_apres ?? p.budget_mad_apres)
  if (avant == null && apres == null) return null
  const delta = (apres ?? 0) - (avant ?? 0)
  return {
    avant, apres, delta,
    direction: delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat',
  }
}

// Motifs de rejet STRUCTURÉS (jamais du chat libre) — proposés dans un select.
export const REJECTION_REASONS = [
  { value: 'hors_budget', label: 'Hors budget' },
  { value: 'mauvais_ciblage', label: 'Ciblage inadapté' },
  { value: 'creatif_non_conforme', label: 'Créatif non conforme (règle de marque)' },
  { value: 'mauvais_moment', label: 'Mauvais moment' },
  { value: 'autre', label: 'Autre' },
]

// Artefact réel porté par l'action (créatif à prévisualiser), ou null.
export function actionCreative(action) {
  if (!action) return null
  const c = action.creative || action.creatif || (action.payload && action.payload.creative)
  if (!c) return null
  return {
    url: c.preview_url || c.file_url || c.url || '',
    designation: c.designation || c.nom || c.name || 'Créatif',
    type: c.type || '',
  }
}

// ── ENG26 — Brief hebdomadaire (que s'est-il passé → pourquoi → suggestion) ──
// Normalise la réponse en { periode, resume, items:[{ id, quoi, pourquoi,
// suggestion, action_id }] }. `action_id` (quand présent) permet à la carte de
// pointer vers la boîte d'approbation (ENG25).
export function normalizeBrief(raw) {
  const b = raw && typeof raw === 'object' ? raw : {}
  const rawItems = Array.isArray(b.items) ? b.items
    : Array.isArray(b.sections) ? b.sections : []
  const items = rawItems.filter(Boolean).map((it, i) => ({
    id: it.id ?? i,
    quoi: it.quoi || it.what || it.titre || '',
    pourquoi: it.pourquoi || it.why || '',
    suggestion: it.suggestion || it.recommandation || '',
    action_id: it.action_id ?? it.engine_action_id ?? null,
  }))
  return {
    periode: b.periode || b.period || '',
    resume: b.resume || b.summary || '',
    items,
  }
}

// La carte pointe-t-elle vers une action à approuver (ENG25) ?
export function briefItemHasAction(item) {
  return !!(item && item.action_id != null)
}

// ── ENG27 — Bibliothèque créative (CreativeAsset + policy-check ENG16) ──
// Policy Taqinor par défaut (repli si l'asset ne porte pas ses propres règles) :
// checklist DÉTERMINISTE que l'humain confirme règle par règle (le système
// enregistre, il n'« évalue » pas seul).
export const DEFAULT_POLICY_RULES = [
  { key: 'no_fake_worksite', label: 'Aucun faux chantier, client ou témoignage' },
  { key: 'no_unverified_figure', label: 'Aucun chiffre non vérifié' },
  { key: 'brand_safe', label: 'Conforme à la marque (explainer / B-roll / rendu produit OK)' },
]

// Un asset est « vérifié » si son policy_stamp est passé (sinon : pending).
export function policyPassed(asset) {
  return !!(asset && asset.policy_stamp && asset.policy_stamp.passed)
}

// Règles à confirmer pour cet asset (ses propres règles ENG16, sinon défaut).
export function assetPolicyRules(asset) {
  const r = asset && Array.isArray(asset.policy_rules) ? asset.policy_rules.filter(Boolean) : null
  return r && r.length ? r : DEFAULT_POLICY_RULES
}

// ── ENG28 — Journal d'actions (timeline EngineAction) ──
export const ACTION_RESULT_LABELS = {
  en_attente: 'En attente',
  approuve: 'Approuvée',
  rejete: 'Rejetée',
  applique: 'Appliquée',
  echec: 'Échec',
}

// Normalise le statut/résultat d'une action en une clé de bucket stable.
export function actionResultKey(action) {
  const s = String(action?.statut ?? action?.result ?? '').toLowerCase()
  if (s.startsWith('approuv')) return 'approuve'
  if (s.startsWith('rejet')) return 'rejete'
  if (s.startsWith('appliqu')) return 'applique'
  if (s.startsWith('echec') || s.startsWith('éch')) return 'echec'
  if (s.startsWith('attente') || s.startsWith('en_attente') || s === 'pending') return 'en_attente'
  return s || 'en_attente'
}

export function actionResultLabel(action) {
  return ACTION_RESULT_LABELS[actionResultKey(action)] || '—'
}

// auto vs manuel : explicite (mode/auto) sinon déduit de la présence d'un
// approbateur humain.
export function actionMode(action) {
  if (!action) return 'auto'
  if (action.mode === 'manuel' || action.mode === 'manual') return 'manuel'
  if (action.mode === 'auto') return 'auto'
  if (action.auto === true) return 'auto'
  if (action.auto === false) return 'manuel'
  return action.approuve_par ? 'manuel' : 'auto'
}

// Filtre pur de la timeline (statut + mode) — testable isolément.
export function filterActionLog(actions, { statut, mode } = {}) {
  return (actions || []).filter(a => {
    if (statut && actionResultKey(a) !== statut) return false
    if (mode && actionMode(a) !== mode) return false
    return true
  })
}

// ── ENG39 — Expérimentations (bandit) : posteriors lisibles par un humain ──
// Pourcentage (fraction 0..1 → « 72 % »). L'API donne une PROBABILITÉ (p_best,
// allocation) ; on ne fait que la formater — « — » si la donnée manque.
export function formatPercent(value, decimals = 0) {
  const n = typeof value === 'string' ? Number(value) : value
  if (n === null || n === undefined || !Number.isFinite(n)) return '—'
  return `${formatNumber(n * 100, decimals)} %`
}

// Normalise une expérimentation ENG12 : phases + bras (avec posteriors). Aucun
// chiffre inventé — on ne fait que défensivement lire ceux de l'API.
export function normalizeExperiment(raw) {
  const e = raw && typeof raw === 'object' ? raw : {}
  const phases = (Array.isArray(e.phases) ? e.phases : []).filter(Boolean).map((p, i) => ({
    key: p.key ?? String(i),
    label: p.label || p.nom || p.key || `Phase ${i + 1}`,
    statut: p.statut || '',
    statut_display: p.statut_display || p.statut || '',
  }))
  const bras = (Array.isArray(e.bras) ? e.bras : (Array.isArray(e.arms) ? e.arms : []))
    .filter(Boolean).map((b, i) => ({
      id: b.id ?? i,
      nom: b.nom || b.name || `Bras ${i + 1}`,
      p_best: numOrNull(b.p_best ?? b.prob_best),
      mean: numOrNull(b.mean ?? b.moyenne),
      ci_low: numOrNull(b.ci_low ?? b.ic_bas),
      ci_high: numOrNull(b.ci_high ?? b.ic_haut),
      allocation: numOrNull(b.allocation ?? b.part),
    }))
  return {
    id: e.id,
    nom: e.nom || e.name || '',
    statut_display: e.statut_display || e.statut || '',
    metrique_label: e.metrique_label || e.metrique || 'Métrique',
    metrique_fmt: e.metrique_fmt || 'mad', // 'mad' | 'ratio' | 'percent'
    phases,
    bras,
  }
}

// Le bras avec la plus forte probabilité d'être le meilleur (ou null).
export function bestArm(bras) {
  const list = (bras || []).filter(b => Number.isFinite(b?.p_best))
  if (!list.length) return null
  return list.reduce((best, b) => (b.p_best > best.p_best ? b : best))
}

// Normalise le DecisionLog ENG12 (« pourquoi le moteur a fait X », FR + chiffres).
export function normalizeDecisionLog(raw) {
  if (!raw) return []
  const list = Array.isArray(raw) ? raw : (raw.results || raw.log || raw.decisions || [])
  return (list || []).filter(Boolean).map((d, i) => ({
    id: d.id ?? i,
    phase: d.phase || '',
    phase_label: d.phase_label || d.phase || '',
    quand: d.quand || d.date || d.created_at || '',
    decision_fr: d.decision_fr || d.raison_fr || d.message || '',
    chiffres: (d.chiffres && typeof d.chiffres === 'object') ? d.chiffres : {},
  }))
}

// Filtre pur du DecisionLog par phase — testable isolément.
export function filterDecisionLog(log, { phase } = {}) {
  return (log || []).filter(d => !phase || d.phase === phase)
}

// ── ENG40 — Plan de vol + préflight ADSENG38 ──
// Normalise la réponse du préflight (agrégat de TOUTES les portes d'autonomie) :
// [{ key, label, ok, detail }] + `pret` (toutes vertes) + `manquantes` (labels
// des portes rouges). Tant qu'une porte est rouge, l'autonomie ne peut PAS
// s'activer (structurel). On ne fait que LIRE l'état de l'API — jamais l'inventer.
export function normalizePreflight(raw) {
  const p = raw && typeof raw === 'object' ? raw : {}
  const portes = (Array.isArray(p.portes) ? p.portes : (Array.isArray(p.gates) ? p.gates : []))
    .filter(Boolean).map((g, i) => ({
      key: g.key ?? String(i),
      label: g.label || g.nom || g.key || `Porte ${i + 1}`,
      ok: !!g.ok,
      detail: g.detail || g.raison || '',
    }))
  const pret = typeof p.pret === 'boolean' ? p.pret
    : (portes.length ? portes.every(g => g.ok) : false)
  return { pret, portes, manquantes: portes.filter(g => !g.ok).map(g => g.label) }
}

// Normalise le résultat de validation d'un plan : { ok, raisons[] } — les
// raisons FR d'un refus viennent telles quelles de l'API (jamais fabriquées).
export function normalizeValidation(raw) {
  const v = raw && typeof raw === 'object' ? raw : {}
  const raisons = (Array.isArray(v.raisons) ? v.raisons : (Array.isArray(v.reasons) ? v.reasons : []))
    .filter(Boolean).map(String)
  return { ok: !!v.ok, raisons }
}

// Normalise un gabarit de plan de vol 6 mois : phases avec durée en mois.
export function normalizeFlightTemplate(raw) {
  const t = raw && typeof raw === 'object' ? raw : {}
  const phases = (Array.isArray(t.phases) ? t.phases : []).filter(Boolean).map((p, i) => ({
    key: p.key ?? String(i),
    label: p.label || p.nom || p.key || `Phase ${i + 1}`,
    duree_mois: numOrNull(p.duree_mois ?? p.mois),
  }))
  return { key: t.key, nom: t.nom || t.label || t.key || '', phases }
}

// ── ENG41 — Gestionnaire de backlog (CreativeGenerationBatch par campagne) ──
// Borne une fraction dans [0, 1] (largeur de barre / jauge — présentation).
export function clampRatio(value) {
  const n = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(1, n))
}

// Normalise le backlog par campagne : runway, diversité de hooks, LOTS de
// recombinaisons (chacun approuvable). On ne fait que lire les nombres de l'API.
export function normalizeBacklog(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.results || raw?.campagnes || [])
  return (list || []).filter(Boolean).map((c, i) => ({
    id: c.id ?? i,
    campagne: c.campagne || c.campaign || c.nom || c.name || `Campagne ${i + 1}`,
    runway_jours: numOrNull(c.runway_jours ?? c.runway_days),
    runway_cible: numOrNull(c.runway_cible ?? c.runway_target),
    diversite_hooks: numOrNull(c.diversite_hooks ?? c.hook_diversity),
    lots: (Array.isArray(c.lots) ? c.lots : (Array.isArray(c.batches) ? c.batches : []))
      .filter(Boolean).map((l, j) => ({
        id: l.id ?? j,
        nom: l.nom || l.name || `Lot ${j + 1}`,
        statut: l.statut || '',
        statut_display: l.statut_display || l.statut || 'En attente',
        nb_hooks: numOrNull(l.nb_hooks ?? l.hooks_count),
        assets: (Array.isArray(l.assets) ? l.assets : []).filter(Boolean).map((a, k) => ({
          id: a.id ?? k,
          designation: a.designation || a.nom || a.name || `Asset ${k + 1}`,
        })),
      })),
  }))
}

// Ton de la barre de runway selon combien de jours restent vs la cible.
export function runwayTone(jours, cible) {
  const j = Number(jours); const c = Number(cible)
  if (!Number.isFinite(j) || !Number.isFinite(c) || c <= 0) {
    return { color: '#94a3b8', ratio: 0 }
  }
  const ratio = clampRatio(j / c)
  if (j < c * 0.5) return { color: '#dc2626', ratio } // critique
  if (j < c) return { color: '#d97706', ratio } // à surveiller
  return { color: '#16a34a', ratio } // confortable
}

// ── ENG20/ENG42 — Pacing (enveloppe / burn / projection / état) ──
// Normalise la réponse de pacing : montants + état + détail (lignes de dépense).
export function normalizePacing(raw) {
  const p = raw && typeof raw === 'object' ? raw : {}
  return {
    enveloppe_mad: numOrNull(p.enveloppe_mad ?? p.envelope_mad),
    depense_mad: numOrNull(p.depense_mad ?? p.burn_mad ?? p.spend_mad),
    projection_mad: numOrNull(p.projection_mad ?? p.projected_mad),
    jours_restants: numOrNull(p.jours_restants ?? p.days_left),
    etat: p.etat || p.state || '',
    etat_display: p.etat_display || p.state_display || p.etat || '—',
    lignes: (Array.isArray(p.lignes) ? p.lignes : (Array.isArray(p.detail) ? p.detail : []))
      .filter(Boolean).map((l, i) => ({
        id: l.id ?? i,
        label: l.label || l.campagne || l.jour || `Ligne ${i + 1}`,
        montant_mad: numOrNull(l.montant_mad ?? l.montant ?? l.amount_mad),
      })),
  }
}

// Ton de l'état de pacing (déterministe).
export function pacingStateTone(etat) {
  const s = String(etat || '').toLowerCase()
  if (s.includes('plafond') || s.includes('depass') || s.includes('sur_rythme')) {
    return { bg: '#fee2e2', color: '#991b1b' }
  }
  if (s.includes('sous_rythme') || s.includes('retard')) {
    return { bg: '#fef9c3', color: '#854d0e' }
  }
  return { bg: '#dcfce7', color: '#166534' } // dans le rythme
}

// ── ENG31/ENG42 — Réconciliation Meta-vs-ERP ──
// Normalise les lignes de réconciliation : écart Meta↔ERP + statut. On ne fait
// que LIRE l'écart fourni par l'API — jamais le recalculer/inventer.
export function normalizeReconciliation(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.results || raw?.lignes || [])
  return (list || []).filter(Boolean).map((r, i) => ({
    id: r.id ?? i,
    campagne: r.campagne || r.campaign || r.nom || `Campagne ${i + 1}`,
    meta_mad: numOrNull(r.meta_mad),
    erp_mad: numOrNull(r.erp_mad),
    ecart_mad: numOrNull(r.ecart_mad ?? r.gap_mad),
    ecart_pct: numOrNull(r.ecart_pct ?? r.gap_pct),
    statut: r.statut || r.status || '',
    statut_display: r.statut_display || r.statut || '—',
    lignes: (Array.isArray(r.lignes) ? r.lignes : (Array.isArray(r.detail) ? r.detail : []))
      .filter(Boolean).map((l, j) => ({
        id: l.id ?? j,
        label: l.label || l.jour || l.date || `Ligne ${j + 1}`,
        meta_mad: numOrNull(l.meta_mad),
        erp_mad: numOrNull(l.erp_mad),
      })),
  }))
}

// Ton du statut de réconciliation (ok / écart / alerte).
export function reconStatusTone(statut) {
  const s = String(statut || '').toLowerCase()
  if (s.includes('alerte') || s.includes('critique')) return { bg: '#fee2e2', color: '#991b1b' }
  if (s.includes('ecart') || s.includes('écart') || s.includes('gap')) return { bg: '#fef9c3', color: '#854d0e' }
  return { bg: '#dcfce7', color: '#166534' } // ok / réconcilié
}

// ── ENG14/ENG43 — Règles (gabarits) & dry-run ──
// Normalise un gabarit de règle (picker FR — jamais un builder libre) :
// condition FR → action FR, en clair.
export function normalizeRuleTemplate(raw) {
  const t = raw && typeof raw === 'object' ? raw : {}
  return {
    key: t.key ?? t.id,
    nom: t.nom || t.name || t.label || 'Règle',
    description: t.description || t.desc || '',
    condition_fr: t.condition_fr || t.condition || '',
    action_fr: t.action_fr || t.action || '',
  }
}

// Normalise le résultat d'un dry-run : résumé FR + objets touchés avec l'effet
// FR de la règle sur chacun (jamais appliqué — juste simulé/visualisé).
export function normalizeDryRun(raw) {
  const d = raw && typeof raw === 'object' ? raw : {}
  return {
    resume_fr: d.resume_fr || d.summary_fr || '',
    objets_touches: (Array.isArray(d.objets_touches) ? d.objets_touches
      : (Array.isArray(d.affected) ? d.affected : [])).filter(Boolean).map((o, i) => ({
        id: o.id ?? i,
        nom: o.nom || o.name || `Objet ${i + 1}`,
        effet_fr: o.effet_fr || o.effect_fr || o.effet || '',
      })),
  }
}

// ── ENG16/ENG43 — Anomalies (flux) avec sévérités ──
// Réutilise `alertTone` (vocabulaire critique/alerte/info commun aux alertes).
export function normalizeAnomalies(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.results || raw?.anomalies || [])
  return (list || []).filter(Boolean).map((a, i) => ({
    id: a.id ?? i,
    titre: a.titre || a.title || 'Anomalie',
    severite: a.severite || a.severity || a.niveau || 'info',
    message: a.message || a.detail || '',
    quand: a.quand || a.date || a.created_at || '',
  }))
}

// ── ENG36/ENG44 — Rapport de simulation (rejeu visuel) ──
// Normalise un rapport de simulation ENG36 : scénarios (avec verdict),
// allocations dans le temps (budget par bras à chaque étape), décisions
// annotées (FR + chiffres). L'outil de confiance fondateur AVANT tout dirham
// réel — on ne fait que LIRE ce que la simulation a produit.
export function normalizeSimReport(raw) {
  const s = raw && typeof raw === 'object' ? raw : {}
  return {
    id: s.id,
    nom: s.nom || s.name || '',
    cree_le: s.cree_le || s.created_at || '',
    scenarios: (Array.isArray(s.scenarios) ? s.scenarios : []).filter(Boolean).map((sc, i) => ({
      key: sc.key ?? String(i),
      nom: sc.nom || sc.name || `Scénario ${i + 1}`,
      verdict: sc.verdict || '',
      verdict_display: sc.verdict_display || sc.verdict || '—',
      resume_fr: sc.resume_fr || sc.summary_fr || '',
    })),
    allocations: (Array.isArray(s.allocations) ? s.allocations : []).filter(Boolean).map((a, i) => ({
      etape: a.etape ?? (i + 1),
      label: a.label || a.date || a.jour || `Étape ${a.etape ?? (i + 1)}`,
      bras: (Array.isArray(a.bras) ? a.bras : (Array.isArray(a.arms) ? a.arms : []))
        .filter(Boolean).map((b, j) => ({
          nom: b.nom || b.name || `Bras ${j + 1}`,
          budget_mad: numOrNull(b.budget_mad ?? b.budget ?? b.montant_mad),
        })),
    })),
    decisions: (Array.isArray(s.decisions) ? s.decisions : []).filter(Boolean).map((d, i) => ({
      id: d.id ?? i,
      etape: d.etape ?? null,
      label: d.label || d.date || d.jour || (d.etape != null ? `Étape ${d.etape}` : ''),
      decision_fr: d.decision_fr || d.raison_fr || d.message || '',
      chiffres: (d.chiffres && typeof d.chiffres === 'object') ? d.chiffres : {},
    })),
  }
}

// Ton du verdict d'un scénario de simulation (gagnant / perdant / neutre).
export function verdictTone(verdict) {
  const v = String(verdict || '').toLowerCase()
  if (v.includes('gagn') || v.includes('positif') || v.includes('succes') || v.includes('succès') || v.includes('vert')) {
    return { bg: '#dcfce7', color: '#166534' }
  }
  if (v.includes('perd') || v.includes('negat') || v.includes('échec') || v.includes('echec') || v.includes('rouge')) {
    return { bg: '#fee2e2', color: '#991b1b' }
  }
  return { bg: '#f1f5f9', color: '#475569' }
}
