// COP-F1 — logique PURE des cartes de l'assistant (contrat
// `backend/django_core/apps/agent/contract_samples/assistant_reponse.json`).
//
// Principe : une carte ne vient JAMAIS du texte libre du modèle. L'écran ne lit
// que `cartes[]` de la réponse (et `carte` / `suite.cartes` de `/confirm`) ; le
// repli sur `proposal` / `result` ne sert qu'à un serveur plus ancien qui ne
// renvoie pas `cartes`. Ce module n'a AUCUNE dépendance (ni React, ni DOM, ni
// store) : il est testé tel quel, avec les échantillons du contrat.

/** Durée de vie d'une proposition quand le serveur ne la dit pas (secondes). */
export const DUREE_PROPOSITION_DEFAUT_S = 300

/** États d'une carte « proposition » — chacune a LE SIEN. */
export const ETATS = Object.freeze({
  A_CONFIRMER: 'a_confirmer',
  EN_COURS: 'en_cours',
  CONFIRMEE: 'confirmee',
  EXPIREE: 'expiree',
  ANNULEE: 'annulee',
  ECHEC: 'echec',
  // Sans réponse du serveur (ou 5xx) : le jeton a pu être consommé et l'action
  // faite — ni confirmable de nouveau, ni dite « non exécutée ».
  INCERTAIN: 'incertain',
})

/** Phrase d'une confirmation au résultat incertain (COP-A3 côté relais). */
export const MESSAGE_INCERTAIN = 'Résultat incertain : vérifie si l’action a été faite avant de la redemander.'

/** Cartes de résultat que l'écran sait rendre (miroir de `CARTES`, registre
 *  Django). Toute autre valeur — ou `null` — tombe sur la carte générique. */
export const CARTES_CONNUES = Object.freeze([
  'liste_leads', 'file_touches', 'matin', 'fiche_lead', 'touche', 'suite_touche',
  'wa_message', 'wa_devis', 'document', 'visite', 'diagnostic',
])

/** Au-delà, une carte (touche, aperçu de devis) est RELUE avant d'ouvrir WhatsApp. */
export const AGE_MAX_CARTE_MS = 3 * 60 * 1000

/** Table FIXE des gestes qu'une proposition de touche peut poster. */
export const GESTES_PROPOSITION = Object.freeze(['fait', 'reporter', 'sauter'])

const estObjet = (v) => v != null && typeof v === 'object' && !Array.isArray(v)

// ── Liens sûrs (principe 2) ───────────────────────────────────────────────────
const PREFIXES_WHATSAPP = ['https://wa.me/', 'https://api.whatsapp.com/']

/** Un lien WhatsApp n'est ouvert que s'il commence par un préfixe de confiance. */
export function lienWhatsAppSur(url) {
  if (typeof url !== 'string') return ''
  return PREFIXES_WHATSAPP.some((p) => url.startsWith(p)) ? url : ''
}

/** Identifiant de devis entier > 0, sinon `null` — la seule source d'un lien de
 *  document (`devis_id` d'une carte `document` ou d'une ligne de devis). */
export function idDevisSur(valeur) {
  const n = Number(valeur)
  return Number.isInteger(n) && n > 0 ? n : null
}

// ── Construction des cartes ───────────────────────────────────────────────────
function preparerProposition(carte, recuLe, historique) {
  const duree = Number(carte.expire_dans_s) > 0
    ? Number(carte.expire_dans_s) : DUREE_PROPOSITION_DEFAUT_S
  // Une proposition rechargée de l'historique a forcément vécu : inactive.
  const expireLe = historique || recuLe == null ? 0 : recuLe + duree * 1000
  return {
    ...carte,
    expire_dans_s: duree,
    expire_le: expireLe,
    confirm_token: carte.confirm_token ?? null,
    etat: historique ? ETATS.EXPIREE : ETATS.A_CONFIRMER,
  }
}

/** Cartes servies par le serveur → cartes d'écran (état propre à chaque
 *  proposition). `historique` : rejeu d'un historique rechargé. */
export function preparerCartes(cartes, { recuLe = null, historique = false } = {}) {
  if (!Array.isArray(cartes)) return []
  const prets = []
  for (const carte of cartes) {
    if (!estObjet(carte)) continue
    if (carte.type === 'proposition') prets.push(preparerProposition(carte, recuLe, historique))
    else if (carte.type === 'resultat') {
      // `recu_le` : âge de la donnée (une touche relue si elle a trop vécu).
      prets.push({ ...carte, recu_le: recuLe, donnees: estObjet(carte.donnees) ? carte.donnees : {} })
    }
  }
  return prets
}

// Serveur plus ancien : pas de `cartes`, seulement `proposal` / `result`.
function donneesLegacy(resultat) {
  if (estObjet(resultat.data)) return resultat.data
  // eslint-disable-next-line no-unused-vars -- on retire seulement les clés d'enveloppe
  const { action_key, type, ...reste } = resultat
  return reste
}

function cartesDepuisLegacy(payload, recuLe) {
  const cartes = []
  const proposal = payload?.proposal
  if (estObjet(proposal)) {
    cartes.push({
      type: 'proposition', action_key: proposal.action_key ?? '', libelle: '',
      apercu: proposal.human_preview ?? '', confirm_token: proposal.confirm_token ?? null,
      expire_dans_s: DUREE_PROPOSITION_DEFAUT_S,
    })
  }
  const result = payload?.result
  if (estObjet(result)) {
    cartes.push({
      type: 'resultat', action_key: result.action_key ?? '', libelle: '',
      carte: null, donnees: donneesLegacy(result),
    })
  }
  return preparerCartes(cartes, { recuLe })
}

/** Les cartes d'une réponse `/query` : `cartes` si présent, sinon le repli. */
export function cartesDeReponse(payload, recuLe) {
  if (Array.isArray(payload?.cartes)) return preparerCartes(payload.cartes, { recuLe })
  return cartesDepuisLegacy(payload, recuLe)
}

/** Message agent d'une réponse `/query` (texte + cartes + journal de la note). */
export function messageDeReponse(payload, recuLe = Date.now()) {
  const msg = {
    role: 'agent',
    content: payload?.answer ?? '',
    cartes: cartesDeReponse(payload, recuLe),
    sql_query: payload?.sql_query,
    action_performed: payload?.action_performed ?? false,
  }
  if (payload?.evenement_id != null) msg.evenement_id = payload.evenement_id
  if (payload?.moteur) msg.moteur = payload.moteur
  return msg
}

/** Carte « résultat » d'une confirmation : `carte` du retour, sinon une carte
 *  générique bâtie sur `data` (serveur plus ancien). */
export function carteDeConfirmation(payload) {
  if (estObjet(payload?.carte) && payload.carte.type === 'resultat') {
    return preparerCartes([payload.carte], { recuLe: payload.recu_le ?? null })[0]
  }
  return {
    type: 'resultat', action_key: payload?.action_key ?? '', libelle: '', carte: null,
    donnees: estObjet(payload?.data) ? payload.data : {},
  }
}

/** `suite` de `/confirm` (moteur natif) → nouveau message de l'assistant. */
export function messageDeSuite(suite, recuLe = Date.now()) {
  const msg = {
    role: 'agent',
    content: typeof suite?.answer === 'string' ? suite.answer : '',
    cartes: preparerCartes(suite?.cartes, { recuLe }),
  }
  if (suite?.evenement_id != null) msg.evenement_id = suite.evenement_id
  return msg
}

/** Message local (jamais envoyé au modèle) : une ou plusieurs cartes posées par
 *  un bouton de l'écran, p. ex. « Préparer » sur une rangée de la file. */
export function messageLocal(cartes, recuLe = Date.now()) {
  return { role: 'agent', content: '', local: true, cartes: preparerCartes(cartes, { recuLe }) }
}

// Une carte « touche » rechargée ne garde pas sa proposition (carte-écho) : le
// corps validé hier ne doit plus pouvoir être posté d'un doigt aujourd'hui.
function sansPropositionDeTouche(carte) {
  if (carte.type !== 'resultat' || carte.carte !== 'touche' || carte.donnees.proposition == null) return carte
  return { ...carte, donnees: { ...carte.donnees, proposition: null } }
}

/** Historique rechargé : les cartes sont rejouées, les propositions inactives. */
export function messagesDeLHistorique(liste) {
  return liste.map((m) => (m?.role === 'agent'
    ? { ...m, cartes: preparerCartes(m.cartes, { historique: true }).map(sansPropositionDeTouche) }
    : m))
}

/** Une proposition a-t-elle dépassé sa durée de vie ? */
export function propositionPerimee(carte, maintenant = Date.now()) {
  return carte?.etat === ETATS.A_CONFIRMER && carte.expire_le > 0 && maintenant >= carte.expire_le
}

/** L'état À AFFICHER d'une proposition (l'expiration se lit à l'écran). */
export function etatAffiche(carte, maintenant = Date.now()) {
  if (carte?.etat === ETATS.A_CONFIRMER
      && (carte.expire_le === 0 || propositionPerimee(carte, maintenant))) {
    return ETATS.EXPIREE
  }
  return carte?.etat ?? ETATS.EXPIREE
}

/** FOYER de la conversation : identifiant de la touche de la dernière carte
 *  « touche » affichée, ou `null`. */
export function foyerTouche(messages) {
  if (!Array.isArray(messages)) return null
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const cartes = messages[i]?.cartes
    if (!Array.isArray(cartes)) continue
    for (let j = cartes.length - 1; j >= 0; j -= 1) {
      const c = cartes[j]
      if (c?.type === 'resultat' && c.carte === 'touche') {
        const id = Number(c.donnees?.touche?.id)
        if (Number.isInteger(id) && id > 0) return id
      }
    }
  }
  return null
}
