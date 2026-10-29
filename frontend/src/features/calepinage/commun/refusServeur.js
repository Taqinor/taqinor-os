/* ============================================================================
   ACAL279 (C-ACAL-143) — UN SEUL décodeur des refus serveur du module.
   ----------------------------------------------------------------------------
   Les formes RÉELLES (core/exceptions.taqinor_exception_handler) :
     400 {approbation: ['…'], error: {code, message, fields, request_id}}
     400 {feu_vert: ['…']} · 400 {releve_le: '…'}
     403/404 {detail, error: {…}} · 409 {roof_layout: ['… verrouillé …']}
   `refusServeur(erreur)` → `{ message, champs }` :
     * `message` : `detail`, sinon le premier champ texte (ou liste de
       chaînes), sinon `error.message` ; `''` quand le serveur n'a rien dit ;
     * `champs` : `{clé: texte}` de chaque champ nommé — la clé `error`
       (enveloppe du handler) n'est JAMAIS un champ, `detail` non plus.
   Jamais un objet rendu tel quel (« Objects are not valid as a React child »).
   ========================================================================== */

/** Un texte lisible : chaîne non vide, ou première chaîne d'une liste. */
function texte(valeur) {
  if (typeof valeur === 'string') return valeur.trim()
  if (Array.isArray(valeur)) {
    const chaines = valeur.filter((v) => typeof v === 'string' && v.trim())
    return chaines.map((v) => v.trim()).join(' ')
  }
  return ''
}

const CLES_HORS_CHAMP = new Set(['error', 'detail'])

export function refusServeur(erreur) {
  const data = erreur?.response?.data
  if (typeof data === 'string') return { message: data.trim(), champs: {} }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return { message: '', champs: {} }
  }
  const champs = {}
  for (const [cle, valeur] of Object.entries(data)) {
    if (CLES_HORS_CHAMP.has(cle)) continue
    const t = texte(valeur)
    if (t) champs[cle] = t
  }
  const premier = Object.values(champs)[0] || ''
  const message = texte(data.detail) || premier || texte(data.error?.message)
  return { message, champs }
}

/** Le motif serveur, sinon `repli` (seulement quand le serveur n'a rien dit). */
export function messageRefus(erreur, repli = '') {
  return refusServeur(erreur).message || repli
}
