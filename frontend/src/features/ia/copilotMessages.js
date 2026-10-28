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

// Contexte transmis à /sql-agent/query : celui de l'événement s'il existe,
// sinon le chemin courant. `lead_id` n'est gardé que s'il est un entier > 0.
export function contexteEcran(detail, cheminCourant) {
  const ecran = (detail && typeof detail.ecran === 'string' && detail.ecran) || cheminCourant || '/'
  const lead = Number(detail?.lead_id)
  return { ecran: ecran.slice(0, 255), lead_id: Number.isInteger(lead) && lead > 0 ? lead : null }
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
