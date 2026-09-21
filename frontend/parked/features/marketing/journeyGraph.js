/* ============================================================================
   NTMKT13 — Logique PURE du canevas de journey (sérialisation nœuds/arcs).
   ----------------------------------------------------------------------------
   Séparée du composant pour être testable sans DOM (même patron que
   `segmentRules.js`). Le contrat de données est EXACTEMENT celui livré par
   NTMKT12 (`/marketing/noeuds-journey/`, `/marketing/arcs-journey/`) :
   nœud = {id, sequence, type_noeud, libelle, position_x, position_y, config},
   arc  = {id, source, cible, condition, valeur, ordre}. Aucune forme
   inventée côté écran — une seule source de vérité.
   ========================================================================== */

export const TYPES_NOEUD = [
  { key: 'declencheur', label: 'Déclencheur' },
  { key: 'attente', label: 'Attente (J+n)' },
  { key: 'attente_jusqu_a', label: "Attente jusqu'à" },
  { key: 'action', label: 'Action (message / CRM)' },
  { key: 'branche', label: 'Branche' },
  { key: 'sortie', label: 'Sortie' },
]

export const CANAUX_ACTION = [
  { key: 'email', label: 'Email' },
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'appel', label: 'Appel' },
]

export const CONDITIONS_ARC = [
  { key: 'toujours', label: 'Toujours' },
  { key: 'a_ouvert', label: 'A ouvert' },
  { key: 'a_clique', label: 'A cliqué' },
  { key: 'score_seuil', label: 'Score >= seuil' },
  { key: 'tag_present', label: 'Tag présent' },
]

// Conditions qui portent une valeur libre (seuil, nom de tag).
export const CONDITIONS_AVEC_VALEUR = ['score_seuil', 'tag_present']

export const TAILLE_NOEUD = { largeur: 150, hauteur: 54 }

/** Ligne API -> nœud d'écran (positions numériques, config toujours objet). */
export function noeudDepuisApi(row) {
  return {
    id: row?.id,
    sequence: row?.sequence,
    type_noeud: row?.type_noeud || 'action',
    libelle: row?.libelle || '',
    x: Number(row?.position_x) || 0,
    y: Number(row?.position_y) || 0,
    config: row?.config && typeof row.config === 'object' ? row.config : {},
  }
}

/** Ligne API -> arc d'écran. */
export function arcDepuisApi(row) {
  return {
    id: row?.id,
    source: row?.source,
    cible: row?.cible,
    condition: row?.condition || 'toujours',
    valeur: row?.valeur || '',
    ordre: Number(row?.ordre) || 1,
  }
}

/** Graphe complet depuis les deux listes API (ordre d'évaluation respecté). */
export function grapheDepuisApi(noeudsRows, arcsRows) {
  const noeuds = (noeudsRows || []).map(noeudDepuisApi)
  const arcs = (arcsRows || [])
    .map(arcDepuisApi)
    .sort((a, b) => (a.ordre - b.ordre) || ((a.id || 0) - (b.id || 0)))
  return { noeuds, arcs }
}

/** Nœud d'écran -> corps POST/PATCH (jamais de `company` : forcée serveur). */
export function payloadNoeud(noeud, sequenceId) {
  return {
    sequence: sequenceId ?? noeud.sequence,
    type_noeud: noeud.type_noeud,
    libelle: noeud.libelle || '',
    position_x: Math.round(noeud.x || 0),
    position_y: Math.round(noeud.y || 0),
    config: noeud.config || {},
  }
}

/** Arc d'écran -> corps POST/PATCH. */
export function payloadArc(arc) {
  return {
    source: arc.source,
    cible: arc.cible,
    condition: arc.condition || 'toujours',
    valeur: CONDITIONS_AVEC_VALEUR.includes(arc.condition)
      ? (arc.valeur || '')
      : '',
    ordre: Number(arc.ordre) || 1,
  }
}

/** Nouveau nœud non encore persisté, posé aux coordonnées du dépôt. */
export function nouveauNoeud(type, x, y) {
  return {
    id: null,
    type_noeud: type,
    libelle: (TYPES_NOEUD.find(t => t.key === type) || {}).label || type,
    x: Math.max(0, Math.round(x || 0)),
    y: Math.max(0, Math.round(y || 0)),
    config: {},
  }
}

/** Prochain `ordre` disponible pour un arc sortant de `sourceId`. */
export function prochainOrdre(arcs, sourceId) {
  const sortants = (arcs || []).filter(a => a.source === sourceId)
  return sortants.reduce((max, a) => Math.max(max, Number(a.ordre) || 0), 0) + 1
}

/**
 * Ajoute un arc si la connexion est légale : pas de boucle sur soi-même, pas
 * de doublon (même source, même cible, même condition). Renvoie la NOUVELLE
 * liste (jamais mutée) — identique en cas de refus.
 */
export function ajouterArc(arcs, { source, cible, condition = 'toujours', valeur = '' }) {
  const liste = arcs || []
  if (!source || !cible || source === cible) return liste
  const existe = liste.some(a =>
    a.source === source && a.cible === cible && a.condition === condition)
  if (existe) return liste
  return [...liste, {
    id: null, source, cible, condition, valeur,
    ordre: prochainOrdre(liste, source),
  }]
}

/** Centre d'un nœud (point d'ancrage des arêtes SVG). */
export function centreNoeud(noeud) {
  return {
    x: (noeud?.x || 0) + TAILLE_NOEUD.largeur / 2,
    y: (noeud?.y || 0) + TAILLE_NOEUD.hauteur / 2,
  }
}

/** Segment SVG entre deux nœuds, ou null si l'un des deux manque. */
export function segmentArc(noeuds, arc) {
  const src = (noeuds || []).find(n => n.id === arc.source)
  const dst = (noeuds || []).find(n => n.id === arc.cible)
  if (!src || !dst) return null
  const a = centreNoeud(src)
  const b = centreNoeud(dst)
  return { x1: a.x, y1: a.y, x2: b.x, y2: b.y }
}

/** Libellé lisible d'un arc (condition + valeur éventuelle). */
export function libelleCondition(arc) {
  const base = (CONDITIONS_ARC.find(c => c.key === arc?.condition) || {}).label
    || arc?.condition || ''
  if (CONDITIONS_AVEC_VALEUR.includes(arc?.condition) && arc?.valeur) {
    return `${base} : ${arc.valeur}`
  }
  return base
}
