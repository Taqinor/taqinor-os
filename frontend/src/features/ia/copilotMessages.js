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
export function canSendQuestion(text, loading) {
  if (loading) return false
  return typeof text === 'string' && text.trim().length > 0
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
