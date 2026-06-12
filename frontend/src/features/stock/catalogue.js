// Taxonomie catalogue : CATÉGORIE → MARQUE → ARTICLES.
// Le groupement d'affichage suit la catégorie RÉELLE du produit (rangée par
// le seeder, ordre délibéré via Categorie.ordre) — jamais l'ordre alphabétique.
// La sélection auto-fill, elle, reste par mots-clés du nom (solar.js) : cette
// couche est purement visuelle et ne peut pas casser le dimensionnement.
import {
  parseWatt, parseKw, parseKwh, parsePhaseIsTri, tauxTvaOf, ttcFromHt,
} from '../ventes/solar.js'

export const MARQUE_GENERIQUE = 'Génériques'

// Spec CLÉ par catégorie — celle qui compte pour choisir l'article.
export function keySpec(p) {
  const cat = p.categorie?.nom ?? ''
  const nom = p.nom ?? ''
  if (cat.startsWith('Panneaux')) {
    const w = parseWatt(nom)
    return w ? `${w} Wc` : null
  }
  if (cat.startsWith('Onduleurs') || cat === 'Variateurs') {
    const kw = parseFloat(p.pompe_kw) || parseKw(nom)
    const phase = p.tension_v
      ? `${p.tension_v} V`
      : (parsePhaseIsTri(nom) ? 'Triphasé' : (/monophas/i.test(nom) ? 'Monophasé' : null))
    if (kw && phase) return `${kw} kW · ${phase}`
    return kw ? `${kw} kW` : phase
  }
  if (cat === 'Batteries') {
    const kwh = parseKwh(nom)
    return kwh ? `${kwh} kWh` : null
  }
  if (cat === 'Pompes') {
    const cv = parseFloat(p.pompe_cv)
    const hmt = parseFloat(p.hmt_m)
    const parts = []
    if (cv) parts.push(`${cv} CV`)
    if (hmt) parts.push(`HMT max ${hmt} m`)
    if (p.courbe_pompe) parts.push('courbe constructeur')
    return parts.join(' · ') || null
  }
  if (cat === 'Câbles') return /m[eè]tre/i.test(nom) ? 'au mètre' : null
  return null
}

export const prixTtc = (p) => ttcFromHt(p.prix_vente, tauxTvaOf(p))
export const sansPrix = (p) => !(parseFloat(p.prix_vente) > 0)

// CATÉGORIE → MARQUE → ARTICLES, ordres délibérés :
// catégories par Categorie.ordre ; marques par nombre d'articles décroissant,
// « Génériques » (sans marque) toujours en dernier.
export function groupCatalogue(produits) {
  const cats = new Map()
  for (const p of produits) {
    const nom = p.categorie?.nom ?? 'Autres'
    const ordre = p.categorie?.ordre ?? 999
    if (!cats.has(nom)) cats.set(nom, { nom, ordre, items: [] })
    cats.get(nom).items.push(p)
  }
  const out = [...cats.values()].sort((a, b) => a.ordre - b.ordre || a.nom.localeCompare(b.nom))
  for (const c of out) {
    const brands = new Map()
    for (const p of c.items) {
      const m = (p.marque || '').trim() || MARQUE_GENERIQUE
      if (!brands.has(m)) brands.set(m, [])
      brands.get(m).push(p)
    }
    c.count = c.items.length
    c.brands = [...brands.entries()]
      .map(([marque, items]) => ({ marque, items }))
      .sort((a, b) => {
        if (a.marque === MARQUE_GENERIQUE) return 1
        if (b.marque === MARQUE_GENERIQUE) return -1
        return b.items.length - a.items.length || a.marque.localeCompare(b.marque)
      })
  }
  return out
}

// Recherche transverse (nom, SKU, marque, catégorie, spec)
export function searchCatalogue(produits, query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return produits
  return produits.filter(p =>
    (p.nom || '').toLowerCase().includes(q)
    || (p.sku || '').toLowerCase().includes(q)
    || (p.marque || '').toLowerCase().includes(q)
    || (p.categorie?.nom || '').toLowerCase().includes(q)
    || (keySpec(p) || '').toLowerCase().includes(q))
}
