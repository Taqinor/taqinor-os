// VX211 — « Ma file » par persona + départage « victoires rapides ».
//
// VX83 construit UNE union de « Ma file » triée par urgence GLOBALE,
// identique pour tous les rôles — or commercial/comptable/technicien/
// directeur ont des priorités radicalement différentes. Ce module pose
// l'ORDRE des `kind` par défaut (persona déduite de `state.auth.role_nom`),
// surchargeable et persisté en `localStorage` — JAMAIS un mur : tous les
// items restent visibles, seul leur ORDRE change (rien n'est filtré/masqué).
//
// Fonctions PURES (testables sans réseau/store) — le composant ne fait que
// lire `state.auth.role_nom` et appeler `sortMaFileItems`.

// Les `kind` connus de l'endpoint `ma-file/` (apps/records/views.py) — un
// `kind` futur non listé ici retombe simplement en fin d'ordre (jamais une
// exception, jamais un item perdu). VX214 ajoute les 4 kinds d'EXÉCUTION
// (chantier_assigne/intervention_du_jour/da_approuvee_a_commander/
// ticket_transfere — jamais une 2ᵉ boîte, ils rejoignent CETTE même liste).
const ALL_KINDS = [
  'activite', 'approbation', 'mention', 'relance', 'lead_chaud', 'devis_expire',
  'chantier_assigne', 'intervention_du_jour', 'da_approuvee_a_commander',
  'ticket_transfere',
]

export const PERSONA_ORDER = {
  // Commercial : relances → leads chauds → devis expirants d'abord.
  commercial: [
    'relance', 'lead_chaud', 'devis_expire', 'activite', 'approbation', 'mention',
    'chantier_assigne', 'intervention_du_jour', 'da_approuvee_a_commander', 'ticket_transfere',
  ],
  // Comptable : factures échues (kind 'activite' côté finance) → approbations.
  comptable: [
    'approbation', 'activite', 'mention', 'relance', 'lead_chaud', 'devis_expire',
    'da_approuvee_a_commander', 'chantier_assigne', 'intervention_du_jour', 'ticket_transfere',
  ],
  // Terrain (technicien/installateur) : interventions du jour → chantiers
  // assignés → tickets transférés d'abord (VX214 — l'exécution du jour).
  terrain: [
    'intervention_du_jour', 'chantier_assigne', 'ticket_transfere', 'da_approuvee_a_commander',
    'activite', 'mention', 'approbation', 'relance', 'lead_chaud', 'devis_expire',
  ],
  // Direction : approbations → escalades d'abord.
  direction: [
    'approbation', 'mention', 'activite', 'relance', 'lead_chaud', 'devis_expire',
    'chantier_assigne', 'intervention_du_jour', 'da_approuvee_a_commander', 'ticket_transfere',
  ],
  // Défaut (rôle non reconnu) : ordre GLOBAL inchangé (urgence pure, aucune
  // priorité de kind — comportement VX83 préservé à l'identique).
  default: ALL_KINDS,
}

export const PERSONA_LABELS = {
  commercial: 'Commercial',
  comptable: 'Comptable',
  terrain: 'Terrain',
  direction: 'Direction',
  default: 'Par défaut',
}

/** Déduit la persona depuis le nom de rôle affiché (`state.auth.role_nom`).
 * Best-effort par mot-clé (pas un enum strict côté backend) : un rôle non
 * reconnu retombe sur `'default'` (ordre global inchangé), jamais une
 * exception. */
export function personaForRoleNom(roleNom) {
  const s = (roleNom || '').toLowerCase()
  if (s.includes('comptable') || s.includes('compta')) return 'comptable'
  if (s.includes('technicien') || s.includes('installateur')) return 'terrain'
  if (s.includes('directeur')) return 'direction'
  if (s.includes('commercial')) return 'commercial'
  return 'default'
}

const STORAGE_KEY_PERSONA = 'taqinor.maFile.personaOverride'
const STORAGE_KEY_QUICKWINS = 'taqinor.maFile.victoiresRapides'

function safeGet(key) {
  try { return window.localStorage?.getItem(key) ?? null } catch { return null }
}
function safeSet(key, value) {
  try { window.localStorage?.setItem(key, value) } catch { /* indisponible : no-op */ }
}
function safeRemove(key) {
  try { window.localStorage?.removeItem(key) } catch { /* indisponible : no-op */ }
}

/** Surcharge persistée : une persona choisie explicitement par l'utilisateur
 * (ex. le rôle déduit du nom ne lui convient pas). `null` = aucune surcharge
 * (l'auto-détection par rôle s'applique). */
export function getPersonaOverride() {
  const v = safeGet(STORAGE_KEY_PERSONA)
  return v && PERSONA_ORDER[v] ? v : null
}
export function setPersonaOverride(persona) {
  if (persona && PERSONA_ORDER[persona]) safeSet(STORAGE_KEY_PERSONA, persona)
  else safeRemove(STORAGE_KEY_PERSONA)
}

/** Préférence persistée « Victoires rapides d'abord » (défaut : désactivée —
 * le tri par défaut, urgence pure au sein d'un même rang de kind, reste
 * inchangé tant que l'utilisateur n'active pas explicitement ce départage). */
export function getQuickWinsPref() {
  return safeGet(STORAGE_KEY_QUICKWINS) === '1'
}
export function setQuickWinsPref(enabled) {
  safeSet(STORAGE_KEY_QUICKWINS, enabled ? '1' : '0')
}

/** Ordre effectif des `kind` pour l'utilisateur courant : la surcharge
 * localStorage gagne sur la persona déduite du rôle. */
export function queueViewForRole(roleNom) {
  const override = getPersonaOverride()
  const persona = override || personaForRoleNom(roleNom)
  return PERSONA_ORDER[persona] || PERSONA_ORDER.default
}

// Départage « Victoires rapides » — correspond à `_EFFORT_ESTIME_PAR_KIND`
// (apps/records/views.py, VX211 backend) ; utilisé seulement en secours si
// un item n'a pas encore `effort_estime` (backend pas encore redéployé).
const EFFORT_RANK_FALLBACK = {
  mention: 0, approbation: 0, activite: 1, relance: 1, lead_chaud: 2, devis_expire: 2,
  da_approuvee_a_commander: 0, intervention_du_jour: 1, ticket_transfere: 1,
  chantier_assigne: 2,
}
const EFFORT_ORDER = { faible: 0, moyen: 1, eleve: 2 }

function effortRank(item) {
  if (item.effort_estime && item.effort_estime in EFFORT_ORDER) {
    return EFFORT_ORDER[item.effort_estime]
  }
  return EFFORT_RANK_FALLBACK[item.kind] ?? 1
}

const URGENCY_RANK = { overdue: 0, today: 1, upcoming: 2 }

function dueKey(due) {
  if (due == null) return [1, '']
  return [0, String(due)]
}

/**
 * Tri « Ma file » par persona : ordre de `kind` (persona) EN PREMIER, puis
 * urgence, puis (si `quickWinsFirst`) l'effort estimé en départage, puis
 * l'échéance. Jamais un filtre — tous les items d'entrée sont dans la
 * sortie, seul l'ORDRE change. Rôle non reconnu / persona 'default' →
 * `PERSONA_ORDER.default` = `ALL_KINDS` dans l'ordre d'origine, donc
 * équivalent au tri d'urgence pur déjà servi par le backend (VX83).
 */
export function sortMaFileItems(items, { roleNom, quickWinsFirst = false } = {}) {
  const order = queueViewForRole(roleNom)
  const kindRank = (kind) => {
    const i = order.indexOf(kind)
    return i === -1 ? order.length : i
  }
  return [...(items || [])].sort((a, b) => {
    const kr = kindRank(a.kind) - kindRank(b.kind)
    if (kr !== 0) return kr
    const ur = (URGENCY_RANK[a.urgency] ?? 3) - (URGENCY_RANK[b.urgency] ?? 3)
    if (ur !== 0) return ur
    if (quickWinsFirst) {
      const er = effortRank(a) - effortRank(b)
      if (er !== 0) return er
    }
    const [da0, da1] = dueKey(a.due)
    const [db0, db1] = dueKey(b.due)
    if (da0 !== db0) return da0 - db0
    return da1 < db1 ? -1 : da1 > db1 ? 1 : 0
  })
}
