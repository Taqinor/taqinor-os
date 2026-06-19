// N20 — Étiquettes & scan : helpers PURS (sans réseau) pour normaliser un
// code scanné/saisi et router la résolution renvoyée par l'API.
//
// Le code encodé dans l'étiquette est un jeton stable `PRODUIT:<id>` /
// `SYSTEME:<id>` (aucune donnée sensible). On normalise ici la saisie d'un
// lecteur de code-barres (espaces, casse, URL collée) AVANT l'appel résolveur.

// Préfixes connus (alignés sur apps/stock/labels.py).
export const KNOWN_PREFIXES = ['PRODUIT', 'SYSTEME']

// Normalise un code scanné/saisi : retire les espaces parasites, met le
// préfixe en majuscules et conserve l'identifiant. Renvoie '' si vide.
export function normalizeCode(raw) {
  const s = String(raw || '').trim()
  if (!s || !s.includes(':')) return s
  const [prefix, ...rest] = s.split(':')
  return `${prefix.trim().toUpperCase()}:${rest.join(':').trim()}`
}

// Vrai si le code a la forme PREFIX:<entier> avec un préfixe connu.
export function isValidCode(raw) {
  const code = normalizeCode(raw)
  const [prefix, id] = code.split(':')
  return KNOWN_PREFIXES.includes(prefix) && /^\d+$/.test(id || '')
}

// À partir d'une réponse résolveur {type, id, label, route, ...}, construit la
// destination de navigation. Pour un produit, on pré-remplit la recherche du
// catalogue avec le SKU (ou le nom) ; pour un système, on ouvre les chantiers.
export function resolveTarget(resolved) {
  if (!resolved || !resolved.route) return null
  if (resolved.type === 'produit') {
    const q = resolved.sku || resolved.label || ''
    return { route: resolved.route, search: q }
  }
  return { route: resolved.route, search: resolved.label || '' }
}
