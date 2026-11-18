// FG350 — Logique PURE du Copilote in-app (CopilotPanel).
//
// Ce module ne dépend NI de React NI du DOM : il regroupe les petits utilitaires
// d'affichage du tiroir conversationnel global pour qu'ils soient testables en
// `node:test`. Le panneau (CopilotPanel.jsx) câble Redux/axios par-dessus en
// réutilisant la slice `ia` existante (`queryAgent` → /sql-agent/query).
//
// EZ16 — message d'erreur FRANÇAIS, jamais du JSON brut. L'extension `.js`
// est EXPLICITE : ce module est testé en `node --test` (sans bundler), qui
// n'invente pas les extensions — sa chaîne d'imports doit rester résolvable
// par Node comme par Vite.
import { frenchError } from '../../lib/frenchError.js'
// Accord des nombres de l'app Tâches (0 et 1 au singulier) : le formateur pur de `features/taches/lib`.
import { accord } from '../taches/lib/textes.js'

// Message FR clair quand la fonctionnalité est key-gated (GROQ_API_KEY absente
// côté service IA). Le backend renvoie alors un texte d'erreur de configuration
// comme réponse — on le reconnaît pour afficher un message net plutôt que le
// dump technique. Identique au comportement de la page AgentChat (L11).
export const CONFIG_MISSING_FR = 'Assistant indisponible (configuration manquante)'

// Vrai si `text` ressemble à une erreur « clé API manquante » (feature gated).
// Lecture tolérante : aucune exception, renvoie false pour les entrées vides.
export function isConfigMissing(text) {
  if (!text || typeof text !== 'string') return false
  const t = text.toLowerCase()
  return (
    (t.includes('groq_api_key') || t.includes('api_key') || t.includes('api key'))
    && (t.includes('manquante') || t.includes('manquant') || t.includes('missing')
        || t.includes('.env') || t.includes('absente'))
  )
}

// Texte à AFFICHER pour un message agent : remplace une réponse « clé manquante »
// par le libellé FR net, sinon renvoie le contenu tel quel (jamais null —
// dégradation gracieuse quand le backend no-op).
export function displayMessageText(msg) {
  const content = (msg && typeof msg.content === 'string') ? msg.content : ''
  if (msg && msg.role === 'agent' && isConfigMissing(content)) {
    return CONFIG_MISSING_FR
  }
  return content
}

// Normalise une erreur de thunk (chaîne, objet `{detail}` ou objet quelconque)
// en message FR affichable. Reconnaît aussi le cas « clé manquante ».
export function formatAgentError(error) {
  if (error == null) return ''
  // EZ16 — le repli sérialisait l'objet d'erreur : du JSON brut jeté à
  // l'utilisateur. Le contrat canonique en tire une phrase française.
  const raw = typeof error === 'string' ? error : frenchError(error, 'Réponse indisponible.')
  if (isConfigMissing(raw)) return CONFIG_MISSING_FR
  return `Erreur : ${raw}`
}

// Garde d'envoi : on n'envoie une question que si elle n'est pas vide (après
// trim) ET qu'aucune requête n'est déjà en vol. Mutualisé entre le bouton
// « Envoyer », la touche Entrée et les suggestions.
// COP2-W2 — `limite` (facultative) : la longueur maximale lue chez le serveur ; une question plus longue
// n'est jamais envoyée (le serveur la refuserait en 422).
export function canSendQuestion(text, loading, limite = null) {
  if (loading) return false
  if (typeof text !== 'string' || text.trim().length === 0) return false
  return !(Number.isInteger(limite) && limite > 0 && text.trim().length > limite)
}

// COP2-W2 — capacités de l'assistant pour CE compte, lues chez le serveur : longueur maximale d'une question
// et pièces jointes images. Absentes (serveur plus ancien, lecture en échec) : 2000 caractères, pas d'image.
export const LIMITE_QUESTION_DEFAUT = 2000
export const IMAGES_MAX = 3
export const CAPACITES_PAR_DEFAUT = Object.freeze({ limite_question: LIMITE_QUESTION_DEFAUT, images_acceptees: false })

export function normaliserCapacites(data) {
  const n = Number(data?.limite_question)
  return {
    limite_question: Number.isInteger(n) && n > 0 ? n : LIMITE_QUESTION_DEFAUT,
    images_acceptees: data?.images_acceptees === true,
  }
}

/** Compteur de caractères : visible à partir de 80 % de la limite ; `depasse` quand la question est trop longue. */
export function etatCompteur(texte, limite = LIMITE_QUESTION_DEFAUT) {
  const n = typeof texte === 'string' ? texte.trim().length : 0
  const max = Number.isInteger(limite) && limite > 0 ? limite : LIMITE_QUESTION_DEFAUT
  return { n, limite: max, visible: n >= max * 0.8, depasse: n > max }
}

/** « [image jointe] » : ce que l'historique montre d'un message de l'utilisateur qui portait des images
 *  (l'image elle-même n'est jamais gardée, seulement leur nombre). */
export function marqueurImages(msg) {
  const n = Number(msg?.images_jointes)
  if (!Number.isInteger(n) || n <= 0) return ''
  return n === 1 ? '[image jointe]' : `[${n} images jointes]`
}

// AIC9 — événement DOM qui ouvre le Copilote avec le contexte de l'écran :
// `window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, { detail: { ecran,
// lead_id, question, envoyer } }))`. Défini UNE fois ici, importé partout
// (fiche lead AIC34 comprise).
export const EVENEMENT_OUVRIR = 'taqinor:assistant:ouvrir'

// COP-F5 — le CONTEXTE de la question, lu AU MOMENT de l'envoi (jamais un état
// resté d'une ouverture précédente) : route courante normalisée (sans requête
// ni fragment ni barre finale), `lead_id` / `devis_id` lus dans la route de la
// fiche ouverte, `touche_id` = foyer de la conversation (dernière carte
// « touche » affichée), `diagnostic` = tampon technique (« Signaler un bug »).
// `detail` (facultatif) = contexte posé par l'écran qui a émis l'événement
// « Demander à l'assistant » — il ne vaut que pour CETTE question.
const RE_LEAD = /^\/crm\/leads\/(\d+)(?:\/|$)/
const RE_DEVIS = /^\/ventes\/devis\/(\d+)(?:\/|$)/

const entierPositif = (v) => {
  const n = Number(v)
  return Number.isInteger(n) && n > 0 ? n : null
}

export function routeNormalisee(chemin) {
  const brut = typeof chemin === 'string' ? chemin.split(/[?#]/)[0] : ''
  const sansFin = brut.length > 1 ? brut.replace(/\/+$/, '') : brut
  return (sansFin || '/').slice(0, 255)
}

export function construireContexte({ chemin, detail = null, foyer = null, diagnostic = null } = {}) {
  const ecran = detail && typeof detail.ecran === 'string' && detail.ecran
    ? routeNormalisee(detail.ecran) : routeNormalisee(chemin)
  return {
    ecran,
    lead_id: entierPositif(detail?.lead_id) ?? entierPositif(RE_LEAD.exec(ecran)?.[1]),
    devis_id: entierPositif(detail?.devis_id) ?? entierPositif(RE_DEVIS.exec(ecran)?.[1]),
    touche_id: entierPositif(foyer),
    diagnostic: diagnostic ?? null,
  }
}

// AIC8 — notes d'une réponse (contrat assistant_evenement.json) : 👍 = 1,
// 👎 et « ça n'a pas répondu » = −1. Le commentaire est borné à 200 car.
export const NOTE_POSITIVE = 1
export const NOTE_NEGATIVE = -1
export const COMMENTAIRE_MAX = 200

// Réduction d'état PURE : le message noté porte sa note, son commentaire et
// `noteEnvoyee` (bouton « merci »). Idempotent : re-noter remplace la note.
export function marquerNote(msg, note, commentaire = null) {
  const texte = typeof commentaire === 'string' ? commentaire.trim().slice(0, COMMENTAIRE_MAX) : ''
  return { ...msg, note, commentaire: texte || null, noteEnvoyee: true }
}

// Entrée (sans Maj) envoie la question.
export function enterSubmits(handleSubmit) {
  return (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }
}

// COP-F7 — début de la question envoyée par « Signaler un bug » (le tampon
// technique du navigateur part avec, dans `contexte.diagnostic`).
export const PHRASE_SIGNALEMENT = 'Signaler un bug :'

// COP-F7 — le message de l'utilisateur dit-il une panne ? Alors le MÊME tampon
// part tout seul. Lecture tolérante (accents, casse) ; un faux positif est
// sans conséquence (le tampon est technique, sans donnée client).
const MOTS_PANNE = [
  'ne marche pas', 'marche pas', 'ne fonctionne pas', 'fonctionne pas', 'erreur', 'bug',
  'bloque', 'rien ne se passe', 'plante', 'planté', 'ne repond pas', 'ne s\'ouvre pas',
  'ne charge pas', 'impossible',
]
const sansAccent = (t) => t.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export function ditUnePanne(texte) {
  if (typeof texte !== 'string' || !texte.trim()) return false
  const t = sansAccent(texte)
  return MOTS_PANNE.some((m) => t.includes(sansAccent(m)))
}

// TCH118 — les QUATRE demandes prêtes de l'app Tâches (api.md §8, textes.md §5.2). Depuis un écran
// `/taches`, un toucher appelle DIRECTEMENT la route déterministe et rend la carte : aucun modèle de
// langage, donc aucune clé d'IA nécessaire. Ce module reste pur (sans import) : le client d'API est
// injecté (`client` = `api/tachesApi`), pour rester testable en `node --test`.
export const DEMANDES_PRETES_TACHES = Object.freeze([
  { question: 'Planifie ma journée', cle: 'taches.plan.proposer', carte: 'plan_propose', lire: 'proposerJournee' },
  { question: 'Aide-moi à prioriser', cle: 'taches.journee.prioriser', carte: 'priorites', lire: 'lirePriorites' },
  { question: 'Range ma liste', cle: 'taches.liste.ranger', carte: 'capture_apercu', lire: 'saisieRapide' },
  { question: 'Où j\'en suis ?', cle: 'taches.journee.point', carte: 'point', lire: 'lirePoint' },
])

// Seule phrase de la réponse de « Planifie ma journée » qui ne dépend d'aucun chiffre du serveur
// (textes.md §5.2) : les nombres, eux, sont sur la carte.
export const PHRASE_PLAN_PROPOSE = 'Rien ne change tant que tu ne gardes pas.'

export const estEcranTaches = (ecran) => typeof ecran === 'string' && /^\/taches(\/|$)/.test(ecran)

// F3 acceptation ERR 3 — le panneau ouvert depuis un écran Tâches (textes.md §5.2, mot pour mot) : sous-titre
// « ouvert depuis {écran} » (noms d'écran de textes.md §2.1 : onglets et ⋯), champ « Écris ou dicte… », et sans
// conversation libre la phrase qui remplace ce champ. Hors des écrans Tâches, rien de ceci n'est lu.
const ECRANS_TACHES = [
  ['/taches/aujourdhui', 'Aujourd\'hui'], ['/taches/a-trier', 'À trier'], ['/taches/projets', 'Projets'],
  ['/taches/agenda', 'Agenda'], ['/taches/revue', 'Revue de la semaine'], ['/taches/rythme', 'Mon rythme'],
  ['/taches/supprimees', 'Supprimées récemment'], ['/taches/reglages', 'Réglages'],
]
export const CHAMP_TACHES = 'Écris ou dicte…'
export const PHRASE_SANS_CONVERSATION = 'La conversation libre n\'est pas branchée sur ce serveur. '
  + 'Les quatre demandes ci-dessus marchent sans elle.'
// Début du message que le service d'IA rend quand son fournisseur n'est pas réglé (clé absente :
// `relais_copilote.MESSAGE_CONFIGURATION`) ; le texte « clé manquante » plus ancien est lu par `isConfigMissing`.
const DEBUT_MESSAGE_CONFIGURATION = 'L\'assistant n\'est pas disponible pour le moment (réglage du serveur)'

/** Le nom de l'écran Tâches de `ecran` (route normalisée) ; « Tâches » pour un écran sans nom propre. */
export function nomEcranTaches(ecran) {
  const route = typeof ecran === 'string' ? ecran : ''
  const trouve = ECRANS_TACHES.find(([prefixe]) => route === prefixe || route.startsWith(`${prefixe}/`))
  return trouve ? trouve[1] : 'Tâches'
}

/** Vrai quand une réponse de la conversation a dit que le fournisseur d'IA n'est pas réglé (aucune clé). */
export function conversationLibreAbsente(messages) {
  return (Array.isArray(messages) ? messages : []).some((m) => m?.role === 'agent' && typeof m.content === 'string'
    && (isConfigMissing(m.content) || m.content.startsWith(DEBUT_MESSAGE_CONFIGURATION)))
}

/**
 * La réponse de « Planifie ma journée » (textes.md §5.2) : « Tu as gardé {e} essentielles. Pour atteindre
 * {objectif}, voici {n} tâches de plus, dans cet ordre. Rien ne change tant que tu ne gardes pas. » ; aucune
 * essentielle : « Pour atteindre {objectif}, voici {n} tâches, dans cet ordre. … ». Tous les nombres viennent du
 * serveur (`journee/proposition/` : objectif et lignes ; `aujourdhui/` : `progression.essentiel_prevues`) ; un
 * nombre absent (mode sans objectif, journée illisible, rien proposé) : la seule phrase sans chiffre.
 */
export function phrasePlanPropose(proposition, journee) {
  const n = Array.isArray(proposition?.proposition) ? proposition.proposition.length : 0
  const objectif = proposition?.objectif?.nb
  const e = journee?.progression?.essentiel_prevues
  if (!Number.isInteger(objectif) || objectif <= 0 || n === 0 || !Number.isInteger(e) || e < 0) return PHRASE_PLAN_PROPOSE
  if (e === 0) return `Pour atteindre ${objectif}, voici ${accord(n, 'tâche')}, dans cet ordre. ${PHRASE_PLAN_PROPOSE}`
  return `Tu as gardé ${accord(e, 'essentielle')}. Pour atteindre ${objectif}, voici ${accord(n, 'tâche')} de plus, `
    + `dans cet ordre. ${PHRASE_PLAN_PROPOSE}`
}

/** La demande prête dite par `question` (texte exact du bouton), ou `null`. */
export function demandePreteTaches(question) {
  const t = typeof question === 'string' ? question.trim() : ''
  return DEMANDES_PRETES_TACHES.find((d) => d.question === t) ?? null
}

/**
 * Exécute une demande prête et rend le message de l'assistant (une carte « résultat »), ou `null`
 * si `question` n'en est pas une, ou si « Range ma liste » n'a aucune tâche À trier à lui donner.
 * `ids` = identifiants À trier, fournis par l'appelant (jamais devinés ici).
 */
export async function lancerDemandePrete(question, { client, ids = [] } = {}) {
  const demande = demandePreteTaches(question)
  if (!demande || !client) return null
  let reponse
  let journee = null
  if (demande.lire === 'saisieRapide') {
    if (!Array.isArray(ids) || ids.length === 0) return null
    reponse = await client.saisieRapide({ ids, apercu: true })
  } else if (demande.carte === 'plan_propose' && typeof client.lireAujourdhui === 'function') {
    // ERR 3 — {e} de la réponse = les essentielles gardées, lues sur la journée au même moment. Une journée
    // illisible ne prive pas de la carte : la réponse retombe sur sa seule phrase sans chiffre.
    const [lue, jour] = await Promise.allSettled([client[demande.lire](), client.lireAujourdhui()])
    if (lue.status === 'rejected') throw lue.reason
    reponse = lue.value
    journee = jour.status === 'fulfilled' ? jour.value?.data : null
  } else {
    reponse = await client[demande.lire]()
  }
  return {
    role: 'agent',
    content: demande.carte === 'plan_propose' ? phrasePlanPropose(reponse.data, journee) : '',
    cartes: [{
      type: 'resultat', action_key: demande.cle, libelle: demande.question,
      carte: demande.carte, donnees: reponse.data,
    }],
  }
}
