// SPL204 — aides partagées de la liste des devis (DevisList.jsx et ses hooks
// sous devisList/). Jamais un import circulaire depuis DevisList.jsx.

// Extrait un message d'erreur lisible (français) d'une réponse DRF. Couvre
// {detail}, les erreurs de champ ({statut: [...]} — ex. garde de remise T17),
// et retombe sur un message générique sinon. Ne JAMAIS afficher de JSON brut.
export function frenchError(err, fallback) {
  const data = err?.response?.data ?? err
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    if (data.detail) return String(data.detail)
    const first = Object.values(data).find(Boolean)
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string') return first
  }
  return fallback
}

// VX222 — « Relancer ce devis » : à partir de l'aperçu WhatsApp EXISTANT (même
// modale, mêmes données), on remplace UNIQUEMENT le texte du message wa.me par
// un RAPPEL (« petit rappel concernant votre devis ») au lieu de l'envoi
// initial. On réutilise le numéro déjà normalisé côté serveur (base de
// `waData.wa_url`, avant le `?text=`) + le lien public déjà émis (`waData.url`),
// donc aucun backend ni duplication de logique de téléphone. Aperçu-puis-clic :
// rien n'est envoyé automatiquement (règle manuel-wa.me fondateur).
export function buildRelanceMessage(waData, reference) {
  const lien = waData?.url || ''
  return `Bonjour, petit rappel concernant votre devis ${reference || ''}${lien ? ' : ' + lien : ''}`.trim()
}
export function buildRelanceWaUrl(waData, reference) {
  if (!waData?.wa_url) return null
  const base = waData.wa_url.split('?')[0]   // https://wa.me/<numéro normalisé>
  return `${base}?text=${encodeURIComponent(buildRelanceMessage(waData, reference))}`
}
