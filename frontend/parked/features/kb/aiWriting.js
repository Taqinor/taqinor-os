// XKB23 — Helpers PURS de l'assistant IA d'écriture & résumé de l'éditeur KB.
// Aucune dépendance réseau/React ici : construit les payloads envoyés à
// `iaApi.kbRedaction` et applique le résultat au texte de l'éditeur
// (remplacement de sélection ou chapeau de résumé). Testable en isolation.

export const AI_ACTIONS = [
  { action: 'generer', label: 'Générer' },
  { action: 'reformuler', label: 'Reformuler' },
  { action: 'corriger', label: 'Corriger' },
  { action: 'traduire_fr_ar', label: 'Traduire FR→AR' },
  { action: 'traduire_ar_fr', label: 'Traduire AR→FR' },
  { action: 'resumer', label: 'Résumer' },
]

// Reconnaît un message d'indisponibilité « clé LLM manquante » (même
// convention que `copilotMessages.isConfigMissing`, dupliquée ici en local
// pur pour ne pas coupler le module kb à features/ia).
export function isKeyMissing(detail) {
  if (!detail || typeof detail !== 'string') return false
  const t = detail.toLowerCase()
  return (
    (t.includes('groq_api_key') || t.includes('api_key') || t.includes('api key'))
    && (t.includes('manquante') || t.includes('manquant') || t.includes('missing') || t.includes('absente'))
  )
}

// Texte à envoyer à l'agent : la sélection si non vide (reformuler/corriger/
// traduire), sinon le corps entier (générer/résumer — ces deux actions
// n'opèrent jamais sur une simple sélection).
export function textForAction(action, { corps, selectionStart, selectionEnd }) {
  const hasSelection = selectionEnd > selectionStart
  if (hasSelection && (action === 'reformuler' || action === 'corriger'
    || action === 'traduire_fr_ar' || action === 'traduire_ar_fr')) {
    return (corps || '').slice(selectionStart, selectionEnd)
  }
  return corps || ''
}

// Applique le résultat de l'agent au corps de l'article :
//  - reformuler/corriger/traduire : remplace la sélection (ou tout le corps
//    si aucune sélection) par le texte reçu.
//  - resumer : préfixe le corps d'un « chapeau » (paragraphe de résumé) sans
//    toucher au reste — sert aussi les articles longs, jamais destructeur.
//  - generer : remplace tout le corps (page vierge) ou l'ajoute à la suite
//    s'il y avait déjà du contenu.
export function applyAiResult(action, result, { corps, selectionStart, selectionEnd }) {
  const hasSelection = selectionEnd > selectionStart
  if (action === 'resumer') {
    const chapeau = (result || '').trim()
    if (!chapeau) return corps
    return `${chapeau}\n\n${corps || ''}`
  }
  if (action === 'generer') {
    return (corps || '').trim() ? `${corps}\n\n${result || ''}` : (result || '')
  }
  // reformuler / corriger / traduire_*
  if (hasSelection) {
    const before = (corps || '').slice(0, selectionStart)
    const after = (corps || '').slice(selectionEnd)
    return `${before}${result || ''}${after}`
  }
  return result || ''
}
