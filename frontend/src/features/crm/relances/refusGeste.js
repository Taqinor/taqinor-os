// Geste d'une touche de relance (Fait / Sauter / Reporter) — la partie commune
// aux trois écrans qui les portent : `RelancesDuJourWidget`, `RelancesSuiviPage`
// et `CadenceFrise`. Une seule copie (garde `check_duplicats_litteraux.py`) :
// un refus NOMMÉ par le serveur se lit ici, une fois, quel que soit le statut.
import crmApi from '../../../api/crmApi'
import { toastError } from '../../../lib/toast'

/** Envoie le geste choisi sur la touche `id` (`fait` | `sauter` | `reporter`). */
async function lancerGesteTouche(action, id, payload) {
  let res
  if (action === 'fait') res = await crmApi.marquerRelanceEtapeFait(id, payload)
  else if (action === 'sauter') res = await crmApi.marquerRelanceEtapeSautee(id, payload)
  else if (action === 'reporter') res = await crmApi.reporterRelanceEtape(id, payload)
  return res
}

/** Vrai quand le serveur a NOMMÉ son refus : 403 (rôle), ou 400/409 portant
 *  `erreurs` (par champ) ou un `detail` non vide (dont « Cette étape est déjà
 *  traitée »). La ligne l'affiche sous le geste ; le panneau reste ouvert. */
export function estRefusNomme(err) {
  const statut = err?.response?.status
  const donnees = err?.response?.data
  return statut === 403 || ((statut === 400 || statut === 409)
    && (Object.keys(donnees?.erreurs ?? {}).length > 0
      || (typeof donnees?.detail === 'string' && donnees.detail !== '')))
}

/** Traite un geste de bout en bout pour un écran : `setBusyId(id)` pendant
 *  l'appel (remis à `null` ensuite, succès ou échec), `surSucces(res)` après la
 *  réponse (relecture de la liste, retrait de la touche…), puis renvoie
 *  `res.data`. Échec : un refus NOMMÉ est relancé tel quel à la ligne (elle
 *  l'affiche sous le geste, le panneau reste ouvert) ; réseau, 5xx et réponse
 *  sans message restent signalés par le toast — l'échec n'est jamais muet. */
export async function traiterGesteTouche({ action, id, payload, setBusyId, surSucces }) {
  setBusyId(id)
  try {
    const res = await lancerGesteTouche(action, id, payload)
    surSucces?.(res)
    return res?.data
  } catch (err) {
    if (!estRefusNomme(err)) toastError('Action impossible pour le moment.')
    throw err
  } finally {
    setBusyId(null)
  }
}
