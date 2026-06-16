// Helpers PURS pour l'édition groupée du catalogue et l'édition en ligne.
// La logique de calcul de prix reflète le backend (apps/stock/views.py
// _bulk_change_prix) pour l'aperçu côté client ; la source de vérité reste le
// serveur. Le PRIX D'ACHAT (prix_achat) n'est jamais touché ni affiché ici.

// Aperçu du nouveau prix de VENTE après variation groupée.
// mode = 'percent' | 'fixed' ; valeur = nombre (peut être négatif).
export function previewNewPrix(prixVente, mode, valeur) {
  const base = Number(prixVente)
  const v = Number(valeur)
  if (!Number.isFinite(base) || !Number.isFinite(v)) return null
  let next
  if (mode === 'percent') next = base * (1 + v / 100)
  else if (mode === 'fixed') next = base + v
  else return null
  if (next < 0) next = 0
  return Math.round(next * 100) / 100
}

// Champs éditables EN LIGNE sur la liste produits (Odoo-style edit-in-place).
// prix_vente / quantite_stock / categorie_id uniquement. Tout le reste passe
// par le formulaire complet. prix_achat est DÉLIBÉRÉMENT exclu (jamais inline,
// jamais client-facing).
export const INLINE_FIELDS = ['prix_vente', 'quantite_stock', 'categorie_id']

// Valide + normalise une saisie inline. Renvoie { ok, value } ou { ok:false, error }.
export function validateInline(field, raw) {
  if (!INLINE_FIELDS.includes(field)) {
    return { ok: false, error: 'Champ non éditable en ligne.' }
  }
  if (field === 'prix_vente') {
    const n = Number(raw)
    if (!Number.isFinite(n) || n < 0) return { ok: false, error: 'Prix invalide.' }
    return { ok: true, value: Math.round(n * 100) / 100 }
  }
  if (field === 'quantite_stock') {
    const n = Number(raw)
    if (!Number.isInteger(n) || n < 0) return { ok: false, error: 'Quantité invalide.' }
    return { ok: true, value: n }
  }
  if (field === 'categorie_id') {
    if (raw === '' || raw == null) return { ok: true, value: null }
    const n = Number(raw)
    if (!Number.isInteger(n) || n <= 0) return { ok: false, error: 'Catégorie invalide.' }
    return { ok: true, value: n }
  }
  return { ok: false, error: 'Champ non éditable en ligne.' }
}
