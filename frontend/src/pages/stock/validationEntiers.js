/* AERR87 — une quantité décimale est REFUSÉE en le disant, jamais tronquée à
   l'entier (« 7.5 » ne devient plus 7 en silence). Patron de
   MouvementsPage::MouvementForm : on juge la valeur RÉELLE tapée, avant tout
   parseInt/Math.floor. */
export const MESSAGE_ENTIER = 'Saisissez une quantité entière.'

/** Vrai si la saisie brute est un entier ≥ 0 (« 7 », jamais « 7.5 ») ; `vide` dit si « » est accepté. */
export function estEntierSaisi(valeur, { vide = false } = {}) {
  const v = String(valeur ?? '').trim()
  return v ? /^\d+$/.test(v) : vide
}

const CHAMPS_ENTIERS_PRODUIT = ['quantite_stock', 'seuil_alerte', 'garantie_mois', 'garantie_production_mois', 'tension_v']

/** Fiche produit : `{champ: message}` pour chaque champ entier (optionnel) mal saisi. */
export function erreursEntiersProduit(fields) {
  return Object.fromEntries(CHAMPS_ENTIERS_PRODUIT
    .filter((nom) => !estEntierSaisi(fields?.[nom], { vide: true }))
    .map((nom) => [nom, 'Saisissez un nombre entier.']))
}

/** Lignes de réception : le message nommant la 1re ligne dont la saisie n'est pas entière, sinon null. */
export function messageSaisieNonEntiere(lignes, valeurDe) {
  const ligne = (lignes ?? []).find((l) => !estEntierSaisi(valeurDe(l), { vide: true }))
  return ligne ? `${MESSAGE_ENTIER} (${ligne.produit_nom ?? 'ligne'})` : null
}
