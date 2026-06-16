// Logique pure (testable) de la liste des devis : filtre d'expiration (T7a) et
// libellé de version (T10). Aucune dépendance React → testable avec node:test.

// Filtre une liste de devis selon le mode d'expiration choisi.
//   'all'    → tout
//   'valide' → seulement les non-expirés (est_expire falsy)
//   'expire' → seulement les expirés (est_expire truthy)
export function filterDevisByExpiry(devis, mode) {
  if (mode === 'expire') return devis.filter(d => !!d.est_expire)
  if (mode === 'valide') return devis.filter(d => !d.est_expire)
  return devis.slice()
}

// Libellé de version « vN » (N>1 seulement, v1 = pas de badge).
export function versionLabel(devis) {
  const v = devis?.version ?? 1
  return v > 1 ? `v${v}` : null
}

// Un devis est-il révisable ? Non s'il a déjà un remplaçant.
export function canRevise(devis) {
  return !devis?.remplace_par
}
