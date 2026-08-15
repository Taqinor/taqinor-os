// NTMOB31 — logique PURE du check-out/check-in d'outillage par scan.
// Aucun React, aucun réseau : on résout un code scanné vers un outil du parc
// déjà chargé, et on décide du statut cible. Le PATCH part ensuite par
// l'endpoint `outillage/outils/{id}/` DÉJÀ existant — aucun nouveau modèle,
// aucune nouvelle règle métier (les seuls statuts touchés sont ceux du parc).

/** Normalise un code scanné : préfixe `OUTIL:` toléré, casse ignorée. */
export function normaliserCode(code) {
  return String(code || '').trim().replace(/^OUTIL:/i, '').toLowerCase()
}

/**
 * Résout un code scanné vers un outil : étiquette d'inventaire (`asset_tag`),
 * n° de série, ou identifiant technique. Renvoie `null` si rien ne correspond —
 * on ne devine JAMAIS un outil approchant.
 */
export function trouverOutil(outils, code) {
  const cible = normaliserCode(code)
  if (!cible) return null
  return outils.find((o) => (
    normaliserCode(o.asset_tag) === cible
    || normaliserCode(o.numero_serie) === cible
    || String(o.id) === cible
  )) || null
}

/**
 * Statut cible d'un scan : « disponible » ↔ « en intervention ».
 * Un outil en réparation ou perdu n'est PAS basculé par un scan (ce sont des
 * décisions humaines, pas un aller-retour de tournée) : on renvoie null.
 */
export function statutApresScan(outil) {
  if (!outil) return null
  if (outil.statut === 'disponible') return 'en_intervention'
  if (outil.statut === 'en_intervention') return 'disponible'
  return null
}
