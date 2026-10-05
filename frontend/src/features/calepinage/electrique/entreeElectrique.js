/* ACAL149/153/154 — ce que les trois onglets « entrée électrique » (Matériel,
   Saisies, Décisions) partagent : la forme d'un refus du serveur et les
   conversions de saisie. Aucune règle métier ici : le serveur est la seule
   autorité (`GET`/`POST calepinages/<pk>/entree-electrique/`, contrat
   `calepinage_entree_electrique.json`). */

/**
 * Les refus 400 du serveur, `{champ: message | [message]}`, rangés `{champ: texte}`. Le
 * message est celui du serveur MOT POUR MOT ; une clé à chemin pointé
 * (`transformateur.perte_a_vide_kw`) est conservée telle quelle pour s'afficher SOUS sa ligne.
 */
export function refusParChamp(donnees) {
  const par = {}
  if (!donnees || typeof donnees !== 'object' || Array.isArray(donnees)) return par
  for (const [cle, message] of Object.entries(donnees)) {
    par[cle] = Array.isArray(message) ? message.join(' ') : String(message)
  }
  return par
}

/** Copie profonde d'une entrée JSON (aucun alias entre l'état de l'écran et la réponse). */
export function copieEntree(valeur) {
  return valeur == null ? valeur : JSON.parse(JSON.stringify(valeur))
}

/** Une saisie numérique → corps posté : un champ vidé vaut `null`, jamais `0` ni `''`. */
export function nombreOuNull(texte) {
  if (texte === null || texte === undefined) return null
  const brut = String(texte).trim().replace(',', '.')
  if (brut === '') return null
  const n = Number(brut)
  return Number.isFinite(n) ? n : null
}

/** Une saisie texte → corps posté : vide ⇒ `null`. */
export function texteOuNull(texte) {
  if (texte === null || texte === undefined) return null
  const brut = String(texte).trim()
  return brut === '' ? null : brut
}
