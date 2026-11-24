// ACAL1905 — une réponse LENTE n'est pas une connexion COUPÉE. Deux gestes de l'atelier en dépendent :
//  (a) la lecture d'un résultat (`GET resultat/`, 5 à 17 s sur une pile chargée) : un délai dépassé se dit
//      « Calcul en cours… » avec « Réessayer » (EtatEcranAtelier), jamais « La connexion a expiré » ;
//  (b) un enregistrement dont la réponse n'est pas revenue : le serveur a pu l'écrire (gunicorn va au bout),
//      l'écran RELIT l'empreinte du document avant de dire quoi que ce soit.
import calepinageApi from '../../api/calepinageApi'

/** Texte unique d'une lecture de résultat qui dépasse son délai (reconnu par EtatEcranAtelier). */
export const MESSAGE_CALCUL_LENT = 'Calcul en cours… le serveur met plus de temps que prévu à répondre.'
export const MESSAGE_RESULTAT_INDISPONIBLE = 'Résultats indisponibles.'

/** Vrai pour un délai dépassé (axios `ECONNABORTED` / `ETIMEDOUT`) : aucune réponse HTTP n'est arrivée. */
export function estDelaiDepasse(err) {
  return !err?.response && (err?.code === 'ECONNABORTED' || err?.code === 'ETIMEDOUT')
}

/** Message d'erreur de la lecture du résultat : un délai dépassé n'accuse pas la connexion. */
export function messageResultatIndisponible(err) {
  return estDelaiDepasse(err) ? MESSAGE_CALCUL_LENT : MESSAGE_RESULTAT_INDISPONIBLE
}

export const ESSAIS_RELECTURE = 3
const ATTENTE_RELECTURE_MS = 1500
const pause = (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms))

/**
 * Après un enregistrement sans réponse : relit l'empreinte « document » du calepinage. Rend la NOUVELLE empreinte si
 * elle diffère de celle envoyée (l'écriture a abouti), sinon `null` (elle n'a pas abouti — ou le serveur ne répond pas
 * encore). Quelques lectures espacées : l'écriture peut encore être en vol au premier essai.
 */
export async function relireEmpreinteApresDelai(calepinageId, empreinteEnvoyee, estLeDocumentEnvoye, attendre = pause) {
  for (let essai = 0; essai < ESSAIS_RELECTURE; essai += 1) {
    if (essai > 0) await attendre(ATTENTE_RELECTURE_MS)
    try {
      const res = await calepinageApi.calepinages.layout(calepinageId)
      const empreinte = res?.data?.empreinte_document
      if (typeof empreinte === 'string' && empreinte && empreinte !== empreinteEnvoyee) {
        // Une empreinte changée n'est NOTRE réussite que si le document relu est celui que nous avons envoyé : un autre
        // onglet ou un collègue a pu écrire entre-temps (notre écriture a alors reçu un 409 arrivé trop tard). Dans ce
        // cas rien n'est dit « enregistré », l'empreinte de l'autre n'est pas adoptée et le prochain essai aura son 409.
        return estLeDocumentEnvoye?.(res?.data?.roof_layout) === true ? empreinte : null
      }
    } catch (err) {
      if (err?.response) return null // un refus du serveur n'est pas un délai : on laisse le message d'origine
    }
  }
  return null
}

/**
 * Lance `ecrire()` ; si sa réponse n'arrive pas dans le délai, relit l'état du serveur. Une empreinte changée = l'écriture a
 * abouti : on rend une réponse `{data: {empreinte_document}}` comme celle que l'écriture aurait rendue. Sinon l'erreur
 * d'origine est relancée (rien n'a été écrit : l'écran peut dire « réessayez »).
 */
export async function ecrireOuRelire(ecrire, calepinageId, empreinteEnvoyee, estLeDocumentEnvoye, attendre = pause) {
  try {
    return await ecrire()
  } catch (err) {
    if (!estDelaiDepasse(err)) throw err
    const relue = await relireEmpreinteApresDelai(calepinageId, empreinteEnvoyee, estLeDocumentEnvoye, attendre)
    if (relue) return { data: { empreinte_document: relue }, headers: {} }
    throw err
  }
}

/**
 * T4-B4-002 — une LECTURE restée sans réponse (délai de 20 s dépassé sur une pile chargée, réseau coupé : le navigateur
 * la montre « annulée ») est relancée par l'écran encore monté, au lieu de laisser un message mort. Un refus SERVI
 * (réponse HTTP avec code) n'est jamais relancé : il se dit tel quel.
 */
export async function lireAvecReprise(lire, essais = 2) {
  let derniere = null
  for (let essai = 0; essai < essais; essai += 1) {
    try {
      return await lire()
    } catch (err) {
      if (err?.response) throw err
      derniere = err
    }
  }
  throw derniere
}
