// FG350 — Logique PURE du Copilote in-app (CopilotPanel).
//
// Ce module ne dépend NI de React NI du DOM : il regroupe les petits utilitaires
// d'affichage du tiroir conversationnel global pour qu'ils soient testables en
// `node:test`. Le panneau (CopilotPanel.jsx) câble Redux/axios par-dessus en
// réutilisant la slice `ia` existante (`queryAgent` → /sql-agent/query).

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
  const raw = typeof error === 'string'
    ? error
    : (error.detail || (() => { try { return JSON.stringify(error) } catch { return String(error) } })())
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
