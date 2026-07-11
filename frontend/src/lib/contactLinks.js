// VX108 — liens tel:/wa.me partagés (extraits de LeadCard.jsx) afin que tout
// écran affichant un numéro de téléphone puisse offrir un lien cliquable
// (tap-to-call / WhatsApp) au lieu d'un simple texte à recomposer.
// Présentation pure : aucune mutation, aucune dépendance externe.

// Numéro de téléphone nettoyé pour un lien tel: (chiffres et + initial).
export function telHref(raw) {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const cleaned = s.replace(/[^\d+]/g, '')
  return cleaned ? `tel:${cleaned}` : null
}

// Numéro de téléphone nettoyé pour un lien wa.me (chiffres uniquement).
export function waHref(raw) {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const digits = s.replace(/\D/g, '')
  return digits ? `https://wa.me/${digits}` : null
}
