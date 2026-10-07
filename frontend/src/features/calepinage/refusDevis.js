/* ============================================================================
   Lot 2 critique #23 / #29 — LE décodeur des refus du pont devis, partagé par
   « Générer / Resynchroniser le devis » (`BoutonDevis`) et l'enregistrement
   de la conception sur la route devis (`ToitureDesign`, resynchro du devis
   lié). Une seule lecture des refus serveur : jamais deux règles pour un même
   comportement. Rien n'est reformulé : on choisit seulement QUEL message
   montrer et on nomme le champ.
   ========================================================================== */

/** Les champs que le pont devis peut nommer, en français lisible. */
export const LIBELLE_CHAMP = {
  roof_layout: 'Conception de toiture',
  composition: 'Composition',
  client: 'Rattachement client',
  calepinage: 'Calepinage',
  devis: 'Devis',
  taux_tva: 'Taux de TVA',
  remise_globale: 'Remise globale',
  detail: 'Devis',
  electrique: 'Verdict électrique',
  derogation_electrique: 'Dérogation électrique',
}

/* ACAL171 (D-ACAL-9) — dérogation « Passer outre » : offerte SEULEMENT à un
   porteur de `calepinage_approuver` (le serveur répond 403 sinon). */
export const MESSAGE_DEROGATION_RESERVEE = 'Dérogation réservée aux approbateurs'
export const MESSAGE_MOTIF_OBLIGATOIRE = 'Saisissez le motif de la dérogation.'

/** Le refus 422 ÉLECTRIQUE (contrat `calepinage_publication_electrique.json`),
 *  ou `null`. */
export function bloquageElectrique(erreur) {
  const data = erreur?.response?.data
  const electrique = data?.electrique
  if (erreur?.response?.status !== 422 || !electrique
    || electrique.verdict !== 'bloquant') return null
  return {
    detail: typeof data.detail === 'string' ? data.detail : '',
    bloquants: Array.isArray(electrique.bloquants) ? electrique.bloquants : [],
    derogationPossible: !!electrique.derogation_possible,
  }
}

export function texteBloquant(b) {
  if (typeof b === 'string') return b
  return String(b?.libelle || b?.code || '')
}

/**
 * Le refus SERVEUR, décomposé en `{champ, message}`. Rien n'est reformulé :
 * on choisit seulement QUEL message montrer quand le serveur en donne
 * plusieurs, et on nomme le champ fautif.
 */
export function refusServeur(erreur) {
  const data = erreur?.response?.data
  if (typeof data === 'string' && data.trim()) {
    return { champ: 'detail', message: data.trim() }
  }
  if (data && typeof data === 'object') {
    if (typeof data.detail === 'string' && data.detail.trim()) {
      return { champ: 'detail', message: data.detail.trim() }
    }
    if (Array.isArray(data.errors) && data.errors.length > 0) {
      return { champ: 'composition', message: String(data.errors[0]) }
    }
    const premier = Object.entries(data).find(([, v]) => v)
    if (premier) {
      const [champ, brut] = premier
      const message = Array.isArray(brut) ? brut.join(' ') : String(brut)
      return { champ, message }
    }
  }
  return {
    champ: 'detail',
    message: 'Le serveur n’a pas répondu. Réessayez dans un instant.',
  }
}
