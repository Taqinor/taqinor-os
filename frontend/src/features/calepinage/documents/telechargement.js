import { refusServeur } from '../commun/refusServeur'

/* Le téléchargement d'un document : décodage du refus serveur (corps BLOB compris), délai
   et options partagés par « Documents » et chaque écran qui télécharge un fichier. */

/** Une erreur serveur -> `[{champ, message}]`, triée pour un affichage
    STABLE. Couvre les DEUX formes vues sur ce module : un objet
    `{champ: message}` et une LISTE de chaînes. Jamais un message générique
    tant qu'un détail existe. ERR-ACON-ERREUR-OBJET-AFFICHEE — l'objet passe
    par LE décodeur du module (`commun/refusServeur`) : l'enveloppe `error` du
    handler global n'est jamais un champ (elle s'affichait « [object Object] »)
    et `detail` est le motif, pas un champ. */
function detailsErreur(donnee) {
  if (Array.isArray(donnee)) {
    return donnee.map((message, index) => ({ champ: String(index + 1), message: String(message) }))
  }
  if (donnee && typeof donnee === 'object') {
    const { message, champs } = refusServeur({ response: { data: donnee } })
    const lignes = Object.entries(champs)
      .map(([champ, texte]) => ({ champ, message: texte }))
      .sort((a, b) => a.champ.localeCompare(b.champ))
    if (message && !Object.values(champs).includes(message)) {
      lignes.unshift({ champ: '', message })
    }
    if (lignes.length) return lignes
  }
  return [{ champ: '', message: 'Le serveur a refusé la demande, sans détail lisible.' }]
}

/* ACAL768 — le délai d'un téléchargement de document : le serveur attend lui-
   même 120 s (gunicorn `--timeout 120`, docker-compose.yml ; nginx
   `proxy_read_timeout 120s`, backend/nginx/nginx.conf) ; la coupure générale
   à 20 s de `api/axios.js` tuait le rapport d'étude PDF avant. */
export const DELAI_TELECHARGEMENT_MS = 120000
export const MINUTES_DE_DELAI = DELAI_TELECHARGEMENT_MS / 60000
export const OPTIONS_TELECHARGEMENT = { timeout: DELAI_TELECHARGEMENT_MS, suppressErrorToast: true }

/** Le corps JSON d'une erreur axios dont la réponse est un BLOB
    (`responseType: 'blob'` — c'est le cas de tout téléchargement de ce
    panneau) : le corps d'erreur voyage lui aussi en blob, il faut le relire
    en texte avant de le parser. Sans réponse du tout (réseau coupé), un motif
    générique — jamais un plantage muet. */
export async function erreurDeTelechargement(erreur, { delai = false } = {}) {
  // ACAL769 — un dépassement du délai de téléchargement dit quoi faire (la
  // durée vient de `DELAI_TELECHARGEMENT_MS`) ; aucun toast global (l'appel
  // porte `suppressErrorToast`).
  if (delai && erreur?.code === 'ECONNABORTED') {
    return [{
      champ: '',
      message: `Le serveur n'a pas fini de préparer ce document en ${MINUTES_DE_DELAI} minutes. `
        + "Réessayez dans une minute ; si cela se répète, signalez-le en donnant l'heure.",
    }]
  }
  const donnees = erreur?.response?.data
  if (typeof Blob !== 'undefined' && donnees instanceof Blob) {
    try {
      return detailsErreur(JSON.parse(await donnees.text()))
    } catch {
      return [{ champ: '', message: 'Réponse du serveur illisible.' }]
    }
  }
  if (donnees) return detailsErreur(donnees)
  return [{ champ: '', message: 'Le serveur est resté injoignable.' }]
}
