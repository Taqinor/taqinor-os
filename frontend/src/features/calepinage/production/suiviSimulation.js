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

const MOTIF_PAR_DEFAUT = 'La simulation a échoué : relancez-la.'

/* T4-V1-012 — un job en échec sur une erreur du SERVEUR (temps dépassé — champ de la fenêtre
   météo, le levier — ou erreur inattendue — aucun champ) se RELANCE : l'écran offre « Réessayer ».
   Un manque de réglage est refusé AVANT le job (409, ACAL940), jamais ici. */
const CHAMPS_RELANCABLES = ['', 'parametres.simulation.fenetre_annees']
/* T4-V1-012 — jamais le nom ou la représentation d'une exception à l'écran (« SoftTimeLimitExceeded() »,
   « KeyError: … ») : un ancien job, ou un serveur plus ancien, peut encore en publier une. */
const RE_EXCEPTION_BRUTE = /^[A-Za-z_][\w.]*(Error|Exception|Exceeded|Interrupt|Timeout)\b|^[A-Za-z_][\w.]*\(.*\)$/

function motifLisible(motif) {
  return RE_EXCEPTION_BRUTE.test(String(motif).trim()) ? MOTIF_PAR_DEFAUT : motif
}

/** Un refus structuré `{champ, motif, relancable}` d'un job `failed` : le premier élément
    nommé publié par le serveur (`elements[0]`), sinon le message d'erreur du
    job, sinon la phrase générique — jamais un champ inventé. */
export function refusDepuisJob(suivi) {
  const premier = Array.isArray(suivi?.elements) ? suivi.elements[0] : null
  const champ = premier && typeof premier.champ === 'string' ? premier.champ : ''
  const motif = premier && typeof premier.motif === 'string' && premier.motif
    ? premier.motif : (suivi?.message_erreur || MOTIF_PAR_DEFAUT)
  return { champ, motif: motifLisible(motif), relancable: CHAMPS_RELANCABLES.includes(champ) }
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
  // ACAL940 — TOUS les manques servis en un seul 409 ({champ, motif, cible}).
  const manquants = Array.isArray(corps.manquants)
    ? corps.manquants.filter((l) => l && typeof l.motif === 'string') : []
  return {
    champ: champ || '',
    motif: (typeof motif === 'string' && motif) || 'Simulation refusée par le serveur.',
    manquants,
    // ACAL1639 — la cible SERVIE du manque de ce champ (`{etape, onglet, champ}` ou `null`).
    cible: manquants.find((l) => l.champ === champ)?.cible ?? null,
  }
}

const PREFIXE_REGLAGE = 'parametres.simulation.'

/** ACAL940 — l'adresse du réglage d'un refus : l'ancre `calx69-<clé>` de
    l'écran des réglages quand le champ en est un, sinon le haut de la page. */
export function lienReglage(champ) {
  return typeof champ === 'string' && champ.startsWith(PREFIXE_REGLAGE)
    ? `/calepinage/reglages#calx69-${champ.slice(PREFIXE_REGLAGE.length)}`
    : '/calepinage/reglages'
}

// ACAL774 — les refus SANS champ de réglage : où agir. `plans` : le module PV se désigne dans
// l'onglet « Matériel électrique » (relu dans `atelier/parcoursGuide.js`) ; `site.pin` : l'épingle se
// pose sur la carte de l'atelier (adresse du calepinage, sans onglet).
const CIBLES_HORS_REGLAGES = {
  plans: { cible: { onglet: 'materiel-electrique' }, libelle: 'Ouvrir le matériel électrique' },
  'site.pin': { cible: {}, libelle: 'Ouvrir la carte de l’atelier' },
}

/** `{cible, libelle}` de l'endroit où agir pour un champ hors réglages ; `null` pour un champ inconnu. */
export function cibleHorsReglages(champ) {
  return typeof champ === 'string' && Object.hasOwn(CIBLES_HORS_REGLAGES, champ)
    ? CIBLES_HORS_REGLAGES[champ] : null
}

// ACAL1639 — l'étape que le SERVEUR nomme pour un manque (`services/manquants_simulation.py::_cible_sans_module` :
// aucun pan → `toit`, pan sans module → `panneaux`) prime sur la table par champ ; cible nulle ou absente : la table.
const GESTES_ETAPE = { toit: 'Tracer le toit', panneaux: 'Poser les panneaux' }

/** `{etape, libelle}` quand la cible servie nomme une étape connue, sinon `cibleHorsReglages(champ)`. */
export function cibleDuManque(champ, cible) {
  const etape = cible?.etape
  return typeof etape === 'string' && Object.hasOwn(GESTES_ETAPE, etape)
    ? { etape, libelle: GESTES_ETAPE[etape] } : cibleHorsReglages(champ)
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

/** ACAL1647 — le libellé du bouton : quand le serveur démontre que la péremption vient d'un
    réglage de la société (son motif l'ouvre ainsi), « Relancer (réglages modifiés) » ; sinon
    le libellé de l'état. Seul le motif servi porte la cause : aucune cause n'est devinée ici. */
export function libelleBouton(etat, motif) {
  if (etat === 'perime' && typeof motif === 'string'
    && motif.startsWith('simulation périmée : un réglage de la société')) return 'Relancer (réglages modifiés)'
  return LIBELLE_BOUTON[etat]
}
