/* ACAL405 — le préfixe des références écrites par « Appliquer aux réglages
   vides » : écrit UNE fois côté écran, égal à `prefixe_reference` du contrat
   `calepinage_profil_depart.json` (un test les compare). */
export const PREFIXE_PROFIL_DEPART = 'Profil de départ — '

export const MENTION_PUBLIEE = 'valeur publiée, non mesurée'

/** Vrai quand la référence figée est celle d'une valeur du profil de départ. */
export const estProfilDepart = (reference) =>
  typeof reference === 'string' && reference.startsWith(PREFIXE_PROFIL_DEPART)
