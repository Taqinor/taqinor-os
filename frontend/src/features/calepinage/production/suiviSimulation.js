/* ============================================================================
   ACAL125 — LE SUIVI D'UN CALCUL DE SIMULATION, UN SEUL VOCABULAIRE.
   ----------------------------------------------------------------------------
   `POST simuler/` rend un accusé 202 `{job_id}`, puis `GET moteur/resultat/<job>/`
   publie le statut RÉEL du travail de fond partagé (`core.models.BackgroundJob`,
   `core/models.py:3210-3213`) : `queued` / `running` / `done` / `failed` — le
   même vocabulaire que `BackgroundJobsBell.jsx`. Les statuts Celery
   (PENDING/STARTED/SUCCESS) n'existent PAS dans cette réponse : les attendre
   faisait lire `queued` comme « terminé sans résultat » et afficher
   « La simulation a échoué. » au premier sondage.

   Ce module est PUR (aucun appel réseau) : il traduit une réponse du serveur
   en une issue (attente / succès / refus structuré) pour les écrans.
   ========================================================================== */

export const STATUTS_EN_ATTENTE = ['queued', 'running']

/** Le travail de fond est-il encore en cours ? (`queued` / `running`). */
export function estEnAttente(statut) {
  return STATUTS_EN_ATTENTE.includes(String(statut || '').toLowerCase())
}

const MOTIF_PAR_DEFAUT = 'La simulation a échoué.'

/** Un refus structuré `{champ, motif}` d'un job `failed` : le premier élément
    nommé publié par le serveur (`elements[0]`), sinon le message d'erreur du
    job, sinon la phrase générique — jamais un champ inventé. */
export function refusDepuisJob(suivi) {
  const premier = Array.isArray(suivi?.elements) ? suivi.elements[0] : null
  if (premier && typeof premier.motif === 'string' && premier.motif) {
    return { champ: typeof premier.champ === 'string' ? premier.champ : '', motif: premier.motif }
  }
  return { champ: '', motif: suivi?.message_erreur || MOTIF_PAR_DEFAUT }
}

/** Le refus 400 de `POST simuler/` : `{champ: [motif]}` — le champ fautif est
    toujours nommé. */
export function refusDepuisErreur(erreur) {
  const corps = erreur?.response?.data
  if (!corps || typeof corps !== 'object') {
    return { champ: '', motif: 'Simulation refusée par le serveur.' }
  }
  const [champ, valeur] = Object.entries(corps)[0] || []
  const motif = Array.isArray(valeur) ? valeur[0] : valeur
  return {
    champ: champ || '',
    motif: (typeof motif === 'string' && motif) || 'Simulation refusée par le serveur.',
  }
}

/** L'issue d'un sondage `moteur/resultat/<job>/` :
    `{etat: 'attente'}` | `{etat: 'succes'}` | `{etat: 'refus', refus}`.
    Un statut inconnu n'est NI un succès NI un refus : on continue d'attendre
    plutôt que de conclure sur un mot qu'on ne connaît pas. */
export function issueDuJob(suivi) {
  const statut = String(suivi?.statut || '').toLowerCase()
  if (statut === 'done') return { etat: 'succes' }
  if (statut === 'failed') return { etat: 'refus', refus: refusDepuisJob(suivi) }
  return { etat: 'attente' }
}

/** Un refus qui se corrige dans l'écran des réglages (société). */
export function refusRenvoieAuxReglages(refus) {
  const champ = typeof refus?.champ === 'string' ? refus.champ : ''
  return champ.startsWith('parametres.') || champ === 'fuseau'
}

/** L'état du bouton unique : jamais simulé → `lancer` ; résultat périmé →
    `perime` ; résultat frais → `frais`. */
export function etatCalcul(data) {
  if (data?.simulation_perimee === true) return 'perime'
  if (data?.simule) return 'frais'
  return 'lancer'
}

export const LIBELLE_BOUTON = {
  lancer: 'Lancer la simulation',
  perime: 'Relancer (document modifié)',
  frais: 'Recalculer',
}
