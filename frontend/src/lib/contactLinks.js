// VX108 — liens tel:/wa.me partagés (extraits de LeadCard.jsx) afin que tout
// écran affichant un numéro de téléphone puisse offrir un lien cliquable
// (tap-to-call / WhatsApp) au lieu d'un simple texte à recomposer.
// Présentation pure : aucune mutation, aucune dépendance externe.
// Extension explicite : module testé sous `node --test` (ESM strict).
import { normalizePhoneE164 } from './format.js'

// Numéro de téléphone nettoyé pour un lien tel: (chiffres et + initial).
export function telHref(raw) {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const cleaned = s.replace(/[^\d+]/g, '')
  return cleaned ? `tel:${cleaned}` : null
}

// QJR635 — LE constructeur de lien wa.me (déménagé de
// features/ventes/clientProposalLink.js, qui le ré-exporte). `digitsE164`
// doit déjà être normalisé (« 2126… ») ; sans numéro → null (jamais un wa.me
// inventé) ; sans texte → pas de `?text=`.
export function buildWaUrl(digitsE164, text) {
  if (!digitsE164) return null
  const base = `https://wa.me/${digitsE164}`
  return text ? `${base}?text=${encodeURIComponent(text)}` : base
}

// QJR635 — lien wa.me depuis un numéro SAISI : normalisé (« 06 61… » →
// 212661…) par `normalizePhoneE164`, sinon gardé seulement s'il est déjà
// international (8 à 15 chiffres sans 0 initial) ; null sinon. Avant, seuls
// les chiffres étaient gardés : « 06 61 23 45 67 » donnait wa.me/0661234567,
// un numéro sans indicatif que WhatsApp ne trouve pas.
export function waHref(raw, text) {
  const s = String(raw ?? '').trim()
  if (!s) return null
  let digits = normalizePhoneE164(s)
  if (!digits) {
    const brut = s.replace(/\D/g, '')
    if (/^[1-9]\d{7,14}$/.test(brut)) digits = brut
  }
  return buildWaUrl(digits, text)
}
