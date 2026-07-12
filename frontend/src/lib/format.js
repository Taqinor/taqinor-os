/* ============================================================================
   F19 — Utilitaires de formatage centralisés (une seule source de vérité)
   ----------------------------------------------------------------------------
   Monnaie MAD, nombres fr-FR, dates jj/mm/aaaa, téléphone marocain. À utiliser
   partout dans l'app à la place des `toLocaleString`/concaténations ad hoc.
   100 % additif : aucun écran existant n'est modifié par ce fichier ; il est
   adopté progressivement (groupes J/P de la refonte).
   ========================================================================== */

const LOCALE = 'fr-FR'

/** Coerce une valeur (number | string fr/en) en nombre fini, sinon null. */
export function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  // Accepte "1 234,56", "1234.56", "1.234,56", "12 %" (incl. espaces insécables)
  const stripped = String(value).replace(/\s|%|MAD|DH|dh/g, '')
  // ERR106 — Un point n'est un séparateur de milliers QUE dans une notation fr
  // où la virgule joue le rôle de séparateur décimal (ex. "1.234,56"). Sans
  // virgule, un point est un vrai point décimal : "1.234" reste 1,234 (et ne
  // devient pas 1234). On ne retire donc les points de milliers que si une
  // virgule décimale est présente.
  const cleaned = (stripped.includes(',')
    ? stripped.replace(/\.(?=\d{3}(\D|$))/g, '') // points de milliers (fr)
    : stripped)
    .replace(',', '.')
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

/**
 * Montant en dirhams marocains. Par défaut 2 décimales, séparateur fr-FR,
 * suffixe « MAD ». `decimals` configurable ; valeur invalide → tiret cadratin.
 */
export function formatMAD(value, { decimals = 2, withSymbol = true } = {}) {
  const n = toNumber(value)
  if (n === null) return '—'
  const body = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n)
  return withSymbol ? `${body} MAD` : body
}

/** Nombre fr-FR (espace fine comme séparateur de milliers, virgule décimale). */
export function formatNumber(value, { decimals } = {}) {
  const n = toNumber(value)
  if (n === null) return '—'
  const opts = {}
  if (decimals !== undefined) {
    opts.minimumFractionDigits = decimals
    opts.maximumFractionDigits = decimals
  }
  return new Intl.NumberFormat(LOCALE, opts).format(n)
}

/** Pourcentage : `formatPercent(19)` → « 19 % » ; `formatPercent(0.5,{decimals:1})` → « 0,5 % ». */
export function formatPercent(value, { decimals = 0 } = {}) {
  const n = toNumber(value)
  if (n === null) return '—'
  const body = new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n)
  return `${body} %`
}

function asDate(value) {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Date jj/mm/aaaa (défaut), ou format long « 18 juin 2026 » si long=true. */
export function formatDate(value, { long = false } = {}) {
  const d = asDate(value)
  if (!d) return '—'
  if (long) {
    return new Intl.DateTimeFormat(LOCALE, {
      day: 'numeric', month: 'long', year: 'numeric',
    }).format(d)
  }
  return new Intl.DateTimeFormat(LOCALE, {
    day: '2-digit', month: '2-digit', year: 'numeric',
  }).format(d)
}

/**
 * Date + heure : « 18/06/2026 14:05 » (défaut), ou « 18 juin 2026, 14:05 »
 * si `long=true` (VX75 — variante lisible utilisée pour les rendez-vous/
 * horodatages destinés à un titre/tooltip plutôt qu'une colonne de tableau).
 */
export function formatDateTime(value, { long = false } = {}) {
  const d = asDate(value)
  if (!d) return '—'
  if (long) {
    return new Intl.DateTimeFormat(LOCALE, {
      day: 'numeric', month: 'long', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(d)
  }
  return new Intl.DateTimeFormat(LOCALE, {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }).format(d)
}

/**
 * VX30 — « il y a X min/h » relatif, extrait de TicketsPage.jsx en util
 * partagé (bandeau de fraîcheur du mur de flotte + chatter tickets). Sous 1
 * min « à l'instant », sous 60 min en minutes, sous 24 h en heures arrondies,
 * au-delà la date jj/mm/aaaa (`formatDate`, jamais un `toLocaleDateString` brut).
 */
export function timeAgo(value) {
  const d = asDate(value)
  if (!d) return '—'
  const mins = Math.round((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return "à l'instant"
  if (mins < 60) return `il y a ${mins} min`
  const h = Math.round(mins / 60)
  if (h < 24) return `il y a ${h} h`
  return formatDate(d)
}

/**
 * Téléphone marocain pour AFFICHAGE.
 * - Local 10 chiffres « 0612345678 » → « 06 12 34 56 78 »
 * - International « +212612345678 » / « 212612345678 » → « +212 6 12 34 56 78 »
 * Chaîne non reconnue renvoyée telle quelle (jamais d'exception).
 */
export function formatPhoneMA(value) {
  if (!value) return ''
  const raw = String(value).trim()
  const digits = raw.replace(/[^\d+]/g, '')
  // International +212 / 00212 / 212
  let intl = null
  if (digits.startsWith('+212')) intl = digits.slice(4)
  else if (digits.startsWith('00212')) intl = digits.slice(5)
  else if (digits.startsWith('212') && digits.length === 12) intl = digits.slice(3)
  if (intl !== null) {
    const d = intl.replace(/\D/g, '').replace(/^0/, '')
    if (d.length === 9) {
      return `+212 ${d[0]} ${d.slice(1, 3)} ${d.slice(3, 5)} ${d.slice(5, 7)} ${d.slice(7, 9)}`
    }
    return raw
  }
  // Local 0XXXXXXXXX (10 chiffres)
  const d = digits.replace(/\D/g, '')
  if (d.length === 10 && d.startsWith('0')) {
    return `${d.slice(0, 2)} ${d.slice(2, 4)} ${d.slice(4, 6)} ${d.slice(6, 8)} ${d.slice(8, 10)}`
  }
  return raw
}

/**
 * Forme canonique marocaine pour STOCKAGE / dédup : « +2126XXXXXXXX » /
 * « +2125XXXXXXXX » quand reconnaissable, sinon les chiffres bruts.
 */
export function canonicalPhoneMA(value) {
  if (!value) return ''
  const digits = String(value).replace(/[^\d+]/g, '')
  let local = null
  if (digits.startsWith('+212')) local = digits.slice(4)
  else if (digits.startsWith('00212')) local = digits.slice(5)
  else if (digits.startsWith('212') && digits.length === 12) local = digits.slice(3)
  else local = digits
  const d = local.replace(/\D/g, '').replace(/^0/, '')
  if (d.length === 9 && (d[0] === '6' || d[0] === '7' || d[0] === '5')) {
    return `+212${d}`
  }
  return String(value).replace(/[^\d+]/g, '')
}

/**
 * Normalise un numéro marocain au format wa.me « 212XXXXXXXXX », ou null si
 * vide/inexploitable. Miroir exact de `normalize_ma_phone`
 * (apps/ventes/utils/phone.py) : sert à VALIDER côté front avant d'appeler les
 * endpoints WhatsApp (un numéro non normalisable → bouton désactivé, pas
 * d'aller-retour 400).
 */
export function normalizeMaPhone(value) {
  if (!value) return null
  let digits = String(value).replace(/\D/g, '') // ne garde que les chiffres
  if (!digits) return null
  if (digits.startsWith('00')) digits = digits.slice(2) // préfixe international 00
  let local
  if (digits.startsWith('212')) local = digits.slice(3)
  else if (digits.startsWith('0')) local = digits.slice(1)
  else local = digits
  local = local.replace(/^0+/, '')
  if (!local) return null
  return '212' + local
}

/**
 * VX122 — Finesse française : pose une espace fine insécable (U+202F) devant
 * `: ; ! ?`, au lieu de l'espace normale (ou de rien) que 116 libellés FR
 * laissent aujourd'hui. Idempotent : une espace normale/insécable/déjà-fine
 * existante devant la ponctuation est remplacée, jamais cumulée.
 * `nbsp('Priorité :').codePointAt(8) === 0x202f`.
 */
export function nbsp(str) {
  if (!str) return str
  return String(str).replace(/[ \t  ]*([:;!?])/g, ' $1')
}

export default {
  toNumber, formatMAD, formatNumber, formatPercent,
  formatDate, formatDateTime, formatPhoneMA, canonicalPhoneMA, normalizeMaPhone, nbsp,
}
