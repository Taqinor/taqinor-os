/* ============================================================================
   UX29–UX33 — Taxonomies de statuts QHSE + helpers PURS (sans JSX).
   ----------------------------------------------------------------------------
   Une seule source de vérité pour les pastilles de statut de chaque ressource
   QHSE, calquée 1:1 sur les `TextChoices` du backend (`apps/qhse/models.py`).
   Les composants `statusPill(map)` sont construits dans `qhsePills.jsx` (JSX) à
   partir de ces cartes ; ce module reste testable au node.
   ========================================================================== */

// Non-conformités (ouverte → en_traitement → resolue → cloturee).
export const NCR_STATUTS = {
  ouverte: { label: 'Ouverte', tone: 'danger' },
  en_traitement: { label: 'En traitement', tone: 'warning' },
  resolue: { label: 'Résolue', tone: 'info' },
  cloturee: { label: 'Clôturée', tone: 'success' },
}

// CAPA (a_faire → en_cours → realisee → verifiee).
export const CAPA_STATUTS = {
  a_faire: { label: 'À faire', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'warning' },
  realisee: { label: 'Réalisée', tone: 'info' },
  verifiee: { label: 'Vérifiée', tone: 'success' },
}

// Audits / plans chantier / procédures — statuts « brouillon → clos/vigueur ».
export const AUDIT_STATUTS = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'warning' },
  clos: { label: 'Clôturé', tone: 'success' },
}

export const PLAN_CHANTIER_STATUTS = {
  en_cours: { label: 'En cours', tone: 'warning' },
  cloture: { label: 'Clôturé', tone: 'success' },
}

export const PROCEDURE_STATUTS = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  en_vigueur: { label: 'En vigueur', tone: 'success' },
  obsolete: { label: 'Obsolète', tone: 'danger' },
}

export const INSPECTION_STATUTS = {
  planifiee: { label: 'Planifiée', tone: 'info' },
  realisee: { label: 'Réalisée', tone: 'success' },
  annulee: { label: 'Annulée', tone: 'neutral' },
}

// Évaluations de risque (document unique).
export const EVAL_RISQUE_STATUTS = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  validee: { label: 'Validée', tone: 'success' },
  archivee: { label: 'Archivée', tone: 'neutral' },
}

// Permis de travail.
export const PERMIS_STATUTS = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  valide: { label: 'Validé', tone: 'success' },
  cloture: { label: 'Clôturé', tone: 'info' },
  expire: { label: 'Expiré', tone: 'danger' },
}

// Consignations LOTO.
export const LOTO_STATUTS = {
  consignee: { label: 'Consignée', tone: 'warning' },
  deconsignee: { label: 'Déconsignée', tone: 'success' },
}

// Incidents HSE.
export const INCIDENT_STATUTS = {
  ouvert: { label: 'Ouvert', tone: 'danger' },
  en_cours: { label: 'En cours', tone: 'warning' },
  clos: { label: 'Clos', tone: 'success' },
}

export const INCIDENT_TYPES = {
  accident: { label: 'Accident', tone: 'danger' },
  presqu_accident: { label: 'Presqu’accident', tone: 'warning' },
  incident: { label: 'Incident', tone: 'info' },
}

// Gravité partagée (NCR + incidents).
export const GRAVITE = {
  mineure: { label: 'Mineure', tone: 'info' },
  majeure: { label: 'Majeure', tone: 'warning' },
  critique: { label: 'Critique', tone: 'danger' },
}

// Déclarations CNSS d'accident du travail.
export const CNSS_STATUTS = {
  a_declarer: { label: 'À déclarer', tone: 'warning' },
  declare: { label: 'Déclaré', tone: 'success' },
  hors_delai: { label: 'Hors délai', tone: 'danger' },
}

// Bordereau de suivi des déchets (BSD).
export const BSD_STATUTS = {
  emis: { label: 'Émis', tone: 'neutral' },
  enleve: { label: 'Enlevé', tone: 'info' },
  traite: { label: 'Traité', tone: 'success' },
  annule: { label: 'Annulé', tone: 'danger' },
}

// Recyclage de modules PV.
export const RECYCLAGE_STATUTS = {
  collecte: { label: 'Collecté', tone: 'neutral' },
  transporte: { label: 'Transporté', tone: 'info' },
  recycle: { label: 'Recyclé', tone: 'success' },
  annule: { label: 'Annulé', tone: 'danger' },
}

// Conformités environnementales.
export const CONFORMITE_STATUTS = {
  conforme: { label: 'Conforme', tone: 'success' },
  a_renouveler: { label: 'À renouveler', tone: 'warning' },
  non_conforme: { label: 'Non conforme', tone: 'danger' },
  expire: { label: 'Expiré', tone: 'danger' },
}

// Bilan carbone.
export const BILAN_STATUTS = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  valide: { label: 'Validé', tone: 'success' },
  archive: { label: 'Archivé', tone: 'neutral' },
}

// Piliers ESG.
export const ESG_PILIERS = {
  e: { label: 'Environnement', tone: 'success' },
  s: { label: 'Social', tone: 'info' },
  g: { label: 'Gouvernance', tone: 'neutral' },
}

/* ── Helpers purs ──────────────────────────────────────────────────────── */

/** Coerce une valeur numérique/chaîne en nombre fini, sinon null. */
export function num(v) {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

/**
 * Taux de fréquence (TF) et de gravité (TG) — miroir exact du calcul backend
 * (`statistiques_tf_tg`). Sert au rendu offline / aux tests ; le cockpit
 * consomme aussi directement les valeurs renvoyées par l'API quand présentes.
 *   TF = (accidents avec arrêt × 1 000 000) / heures travaillées
 *   TG = (jours perdus × 1 000) / heures travaillées
 * Retourne { tf, tg } (null chacun si heures ≤ 0 — jamais de division par zéro).
 */
export function computeTfTg({ accidents = 0, joursPerdus = 0, heures = 0 } = {}) {
  const h = num(heures) ?? 0
  if (h <= 0) return { tf: null, tg: null }
  const acc = num(accidents) ?? 0
  const jours = num(joursPerdus) ?? 0
  const round2 = (x) => Math.round(x * 100) / 100
  return {
    tf: round2((acc * 1_000_000) / h),
    tg: round2((jours * 1_000) / h),
  }
}

/**
 * Gating de clôture fin de chantier : le chantier peut-il clôturer ?
 * Vérité côté serveur (`chantier_peut_cloturer`) — ce helper reflète la même
 * règle pour l'affichage : verdict « passe » ET score ≥ seuil de passage.
 */
export function peutCloturerNotation(notation) {
  if (!notation) return false
  if (notation.peut_cloturer != null) return Boolean(notation.peut_cloturer)
  const score = num(notation.score)
  const seuil = num(notation.seuil_passage)
  if (score === null || seuil === null) return false
  return notation.verdict === 'passe' && score >= seuil
}

/** Niveau de préparation ISO 9001 (miroir des seuils backend ≥85 / ≥60). */
export function isoNiveauLabel(niveau) {
  return (
    { avance: 'Avancé', intermediaire: 'Intermédiaire', initial: 'Initial' }[
      niveau
    ] ?? niveau ?? '—'
  )
}
