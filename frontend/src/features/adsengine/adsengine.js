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
