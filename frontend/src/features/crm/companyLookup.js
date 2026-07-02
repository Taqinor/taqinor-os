// QC1 — Autocomplete entreprise (données propres) + validation de format des
// identifiants marocains + deep-link « Vérifier » vers les registres officiels.
// Fonctions pures (pas d'I/O ici) : la recherche réseau passe par
// crmApi.searchClients côté appelant, qui fournit ses résultats à toMapOptions.

// Provider seam côté FRONT : la source des suggestions est injectée (par défaut
// crmApi.searchClients). QC2 pourra fournir un autre searcher sans changer les
// écrans qui consomment ce module.
export async function searchCompanies(query, { searcher } = {}) {
  const q = (query || '').trim()
  if (!q) return []
  const res = await searcher(q)
  const results = res?.data?.results ?? res?.results ?? res ?? []
  return Array.isArray(results) ? results : []
}

// Map d'un hit backend → option Combobox. La `value` encode la source + l'id
// pour rester unique entre clients/fournisseurs/leads (un client 3 et un lead 3
// ne collisionnent pas). L'option porte le hit complet (pour le remplissage).
export function hitToOption(hit) {
  const srcLabel = hit.source === 'client' ? 'Client'
    : hit.source === 'fournisseur' ? 'Fournisseur'
      : 'Lead'
  const desc = [hit.ice ? `ICE ${hit.ice}` : null, srcLabel]
    .filter(Boolean).join(' · ')
  return { value: `${hit.source}:${hit.id}`, label: hit.nom, description: desc, hit }
}

export function hitsToOptions(hits) {
  return (hits || []).map(hitToOption)
}

// ── Validation NON bloquante des identifiants marocains (avertissements) ─────
const onlyDigits = (v) => String(v ?? '').replace(/\D/g, '')

export function iceWarning(ice) {
  const v = String(ice ?? '').trim()
  if (!v) return null
  return onlyDigits(v).length === 15 ? null
    : "L'ICE comporte normalement 15 chiffres — vérifiez la saisie."
}

export function ifWarning(value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  const d = onlyDigits(v)
  return d.length >= 6 && d.length <= 9 ? null
    : "L'IF semble incomplet — vérifiez la saisie."
}

export function rcWarning(value) {
  const v = String(value ?? '').trim()
  if (!v) return null
  return /\d/.test(v) ? null
    : 'Le RC semble incomplet — vérifiez la saisie.'
}

// ── « Vérifier » : deep-link vers les registres OFFICIELS (nouvel onglet) ────
// Zéro coût, zéro scraping : on ouvre simplement la recherche officielle avec
// le nom tapé pour un copier-coller manuel ponctuel (l'équivalent conforme de
// ce que font les installs Odoo marocaines). Rule #5 : aucune extraction auto.
export function verifierIceUrl(nom) {
  const q = encodeURIComponent((nom || '').trim())
  return `https://www.ice.gov.ma/ICE/RegistreICE.aspx?q=${q}`
}

export function verifierOmpicUrl(nom) {
  const q = encodeURIComponent((nom || '').trim())
  return `https://www.directinfo.ma/?q=${q}`
}
