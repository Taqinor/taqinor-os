// SUIVI-PARCOURS (30/09/2026) — L'ÉCRAN LIT LA TABLE DU PARCOURS.
//
// Avant, `RelanceEtapeRow.jsx` portait ses listes de questions et de réponses
// PAR CADENCE (contact / après devis / réveil / générique) et par libellé de
// visite : les étapes posées par le moteur (« Préparer et envoyer le devis »,
// « Décider la suite », « Rappeler — dernier essai »…) retombaient toutes sur
// la question générique « Où en est ce dossier ? », avec des réponses qui
// n'avaient pas de sens pour elles (« Client refuse » sur « Décider la suite »
// re-posait « Décider la suite » ; « Répondeur » sur « Préparer le devis »…).
//
// Désormais UNE table — `parcours_suivi.json` — dit, pour chaque TYPE d'étape,
// la question et les réponses ; la même table est rejouée par la garde de
// parcours du serveur (`apps/crm/tests_parcours_suivi.py`) et génère le guide
// PDF de la GED. Ce module ne fait que la lire : reconnaître le type d'une
// touche et composer ses réponses. Rien n'est écrit ici — une réponse qui
// n'est pas dans la table n'existe pas à l'écran.
import PARCOURS from './parcours_suivi.json'

const CANAUX_MESSAGE = ['whatsapp', 'email']

/** Le canal « famille » d'une touche : `appel` ou `message`. Le canal
 *  historique « visite » (CAD58) se lit comme un appel. */
export function familleCanal(canal) {
  return CANAUX_MESSAGE.includes(canal) ? 'message' : 'appel'
}

function correspondCanal(type, etape) {
  const canaux = type.reconnaissance?.canaux
  if (!canaux) return true
  const famille = familleCanal(etape.canal)
  return canaux.some((c) => familleCanal(c) === famille)
}

/** Le TYPE d'étape de la table pour cette touche — par CLÉ d'abord (une
 *  société peut renommer un barreau), puis par libellé par défaut (étape posée
 *  avant la clé), puis par cadence + canal. Jamais `null` : le type
 *  `generique` est le repli. */
export function typeEtape(etape) {
  const cle = (etape?.cle || '').trim()
  const libelle = (etape?.libelle || '').trim()
  const types = PARCOURS.etapes
  if (cle) {
    const parCle = types.find((t) => (t.reconnaissance?.cles || []).includes(cle))
    if (parCle) return parCle
  }
  const parLibelle = types.find((t) => (t.reconnaissance?.libelles || []).includes(libelle))
  if (parLibelle) return parLibelle
  const parCadence = types.find((t) => (t.reconnaissance?.cadences || []).includes(etape?.cadence)
    && correspondCanal(t, etape || {}))
  if (parCadence) return parCadence
  return types.find((t) => t.id === 'generique')
}

/** Une réponse COMPLÈTE : le modèle fusionné avec l'entrée de l'étape
 *  (`{...modeles[modele], ...entree}`), plus son identifiant. */
export function reponseComplete(entree) {
  const modele = PARCOURS.modeles[entree.modele] || {}
  return { id: entree.modele, ...modele, ...entree }
}

/** Les réponses que la ligne PROPOSE sur cette touche, dans l'ordre de la
 *  table. Sur le type générique, les précisions d'appel (Répondeur, Occupé,
 *  Numéro invalide, A bloqué) s'ajoutent quand la touche est un appel. */
export function reponsesDeLEtape(type, etape) {
  const reponses = (type.reponses || []).map(reponseComplete)
  if (type.reponses_appel && familleCanal(etape?.canal) === 'appel') {
    // Une entrée est un identifiant de modèle ou un objet `{ modele, effet, suite… }`
    // (l'étape générique décrit ses réponses d'appel : guide + garde les lisent).
    const extras = type.reponses_appel.map((entree) => reponseComplete(
      typeof entree === 'string' ? { modele: entree } : entree))
    // Insérées après la première réponse (« Fait — passer à la suite »),
    // comme les précisions d'appel l'étaient avant : jamais en tête.
    reponses.splice(1, 0, ...extras)
  }
  return reponses
}

/** Une TÂCHE de la commerciale (préparer le devis, décider la suite, planifier
 *  la visite…) : jamais verrouillée « à venir », jamais « sautée ». */
export function estTache(type) {
  return Boolean(type?.tache)
}

/** Une tâche qui n'est PAS un appel au client, même si son barreau porte le
 *  canal « appel » par défaut : ni script d'appel affiché d'office, ni
 *  réponses Répondeur / Occupé. `planifier` reste un appel (caler la date). */
export function estTacheSansAppel(type) {
  return estTache(type) && type.id !== 'planifier'
}

/** Les gestes du panneau, lus dans la table (pour l'écran et les tests). */
export function gestes() {
  return PARCOURS.gestes || []
}

export { PARCOURS }
