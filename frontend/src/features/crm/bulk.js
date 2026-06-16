// Logique PURE des actions en masse sur les leads (T3), isolée du DOM pour être
// testable. La sélection est un Set d'ids ; la règle métier (funnel, garde-fous)
// reste SERVEUR — ici on ne fait que gérer la sélection et formater le bilan.

// Bascule un id dans/hors de la sélection (retourne un NOUVEAU Set).
export function toggleId(selected, id) {
  const next = new Set(selected)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  return next
}

// « Tout sélectionner / tout désélectionner » sur les ids visibles : si tous
// les visibles sont déjà cochés on vide, sinon on coche tous les visibles.
export function toggleAll(selected, visibleIds) {
  const everyVisible = visibleIds.length > 0
    && visibleIds.every((id) => selected.has(id))
  return everyVisible ? new Set() : new Set(visibleIds)
}

// Vrai si tous les ids visibles sont cochés (et il y en a au moins un).
export function allVisibleSelected(selected, visibleIds) {
  return visibleIds.length > 0 && visibleIds.every((id) => selected.has(id))
}

// Restreint la sélection aux ids encore présents (après un refetch/filtre).
export function pruneSelection(selected, presentIds) {
  const present = new Set(presentIds)
  return new Set([...selected].filter((id) => present.has(id)))
}

// Message FR de bilan d'une action en masse à partir de la réponse serveur
// ({updated, unchanged, skipped:[{nom,reason}]}).
export function bulkResultMessage(result) {
  if (!result) return ''
  const parts = []
  if (result.updated) parts.push(`${result.updated} mis à jour`)
  if (result.unchanged) parts.push(`${result.unchanged} inchangé${result.unchanged > 1 ? 's' : ''}`)
  const skipped = result.skipped ?? []
  if (skipped.length) {
    parts.push(`${skipped.length} ignoré${skipped.length > 1 ? 's' : ''}`)
  }
  let msg = parts.join(' · ') || 'Aucune modification'
  if (skipped.length) {
    const details = skipped
      .slice(0, 3)
      .map((s) => `${s.nom} (${s.reason})`)
      .join(' ; ')
    const more = skipped.length > 3 ? ` …et ${skipped.length - 3} autre(s)` : ''
    msg += ` — ${details}${more}`
  }
  return msg
}
