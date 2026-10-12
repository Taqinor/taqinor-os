// VNT44 (Groupe VNT, D-VNT-3) — lecture PURE de l'état de la vente servi par
// le serveur (`d.vente`, contrat `ventes/contract_samples/vente_etat.json`).
// L'écran ne redérive AUCUN geste ni montant : un geste n'est ouvert que si
// `vente.peut.<geste> === true` ; absent (ancien serveur, ligne sans `vente`)
// = fermé, jamais le repli `'libre'` qui ouvrait les boutons sur une version
// remplacée.

/** `vente.peut.<geste>` strictement vrai, sinon faux. */
export function peutVente(d, geste) {
  return d?.vente?.peut?.[geste] === true
}

export function peutFacturerAcompte(d) {
  return peutVente(d, 'facturer_acompte')
}

export function peutFacturerSolde(d) {
  return peutVente(d, 'facturer_solde')
}

export function peutFacturerComplete(d) {
  return peutVente(d, 'facturer_complete')
}

/**
 * Id de la TÊTE de la chaîne de versions qui contient `id`.
 * Le serveur d'abord (`vente.tete_id`), sinon on suit `superseded_by` dans
 * `liste` ; `null` si l'id est inconnu ou si la chaîne boucle.
 */
export function teteDeVersion(liste, id) {
  const lignes = Array.isArray(liste) ? liste : []
  const parId = new Map(lignes.map((d) => [d?.id, d]))
  let courant = parId.get(id)
  if (!courant) return null
  const vus = new Set()
  while (courant) {
    if (courant.vente?.tete_id != null) return courant.vente.tete_id
    if (courant.superseded_by == null) return courant.id
    if (vus.has(courant.id)) return null
    vus.add(courant.id)
    const suivant = parId.get(courant.superseded_by)
    // Successeur hors de la liste : c'est lui la tête connue.
    if (!suivant) return courant.superseded_by
    courant = suivant
  }
  return null
}
