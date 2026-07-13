// VX237 — Collage intelligent : parseurs PURS (zéro dépendance React, zéro
// dépendance externe) consommés par `hooks/usePasteClean.js`. Séparés dans
// leur propre module pour rester testables tels quels avec `node --test`
// dans les worktrees sans `node_modules` (react non disponible).
import { canonicalPhoneMA } from './format.js'

/**
 * Nettoie un numéro de téléphone/WhatsApp collé (espaces, points, tirets,
 * parenthèses...) vers la forme canonique de stockage `+2126XXXXXXXX` /
 * `+2125XXXXXXXX` / `+2127XXXXXXXX`. Retourne `null` si le texte collé ne
 * ressemble à aucun numéro marocain reconnaissable (laisse le collage natif
 * agir — jamais de valeur inventée).
 */
export function parsePastedPhone(text) {
  if (!text) return null
  const trimmed = String(text).trim()
  // Un minimum de chiffres pour ne pas confondre avec un texte quelconque
  // (ex: un nom collé par erreur dans le mauvais champ).
  const digitCount = (trimmed.match(/\d/g) || []).length
  if (digitCount < 9) return null
  const canonical = canonicalPhoneMA(trimmed)
  // canonicalPhoneMA renvoie les chiffres bruts (sans '+') quand la forme
  // n'est pas reconnaissable — dans ce cas on préfère laisser le collage
  // natif plutôt qu'imposer une valeur non canonique.
  if (!canonical || !canonical.startsWith('+212')) return null
  return canonical
}

/**
 * Nettoie un montant collé (Excel « 12 500,00 », « 12.500,00 », « 12500 DH »,
 * « 12 500 MAD »...) vers une chaîne numérique simple consommable par un
 * `<input type="number">` (point décimal, sans séparateur de milliers, sans
 * suffixe devise). Retourne `null` si aucun nombre n'est reconnaissable.
 */
export function parsePastedAmount(text) {
  if (!text) return null
  let cleaned = String(text).trim()
    // Suffixes/préfixes devise usuels — jamais silencieusement ignorés pour
    // un texte qui n'en contient pas.
    .replace(/\b(dh|dhs|mad)\b/gi, '')
    .replace(/\s+/g, '')
  if (!cleaned) return null
  // Un seul séparateur virgule + pas de point → virgule décimale (FR/Excel).
  const hasComma = cleaned.includes(',')
  const hasDot = cleaned.includes('.')
  if (hasComma && !hasDot) {
    // "12500,00" (décimale) vs "12,500" (milliers, rare en FR) : on traite la
    // virgule comme décimale — convention Excel FR dominante dans ce marché.
    cleaned = cleaned.replace(',', '.')
  } else if (hasComma && hasDot) {
    // "12.500,00" (milliers=point, décimale=virgule) : retire les points de
    // milliers, la virgule devient le point décimal.
    cleaned = cleaned.replace(/\./g, '').replace(',', '.')
  }
  if (!/^\d+(\.\d+)?$/.test(cleaned)) return null
  const num = Number(cleaned)
  if (!Number.isFinite(num)) return null
  // Forme "propre" : entier sans zéros inutiles, décimal sinon (jamais de
  // notation scientifique, jamais de séparateur de milliers réinjecté).
  return String(num)
}

// VX237 — mode « carte de visite » : un texte multi-lignes/segments du genre
// « Nom Ahmed Alami Tel 0612345678 » ou « Ahmed Alami — 06 12 34 56 78 »
// collé dans le champ Nom. On ne répartit JAMAIS silencieusement : ce
// parseur ne fait que DÉTECTER un nom + un téléphone plausibles ; l'appelant
// affiche un bouton « Répartir » qui n'agit qu'après confirmation explicite.
const CARD_PHONE_RE = /(\+?\d[\d .()-]{7,}\d)/
const CARD_LABELS_RE = /\b(nom|name|t[ée]l(?:[ée]phone)?|whatsapp|wa|gsm)\s*[:-]?\s*/gi

export function parsePasteCard(text) {
  if (!text) return null
  const trimmed = String(text).trim()
  if (!trimmed.includes('\n') && trimmed.length < 6) return null
  const phoneMatch = trimmed.match(CARD_PHONE_RE)
  if (!phoneMatch) return null
  const telephone = parsePastedPhone(phoneMatch[1])
  if (!telephone) return null
  // Le nom = tout ce qui reste une fois le téléphone et les libellés de champ
  // retirés (multi-lignes aplaties en un seul espace).
  const nom = trimmed
    .replace(phoneMatch[1], ' ')
    .replace(CARD_LABELS_RE, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!nom) return null
  return { nom, telephone }
}
