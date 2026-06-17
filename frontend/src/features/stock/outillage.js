// F1 — Outillage (équipement durable) : libellés & options partagés.
// Pur (aucun React/DOM) → testé par outillage.test.mjs.

export const OUTIL_EMPLACEMENTS = [
  { key: 'depot', label: 'Dépôt' },
  { key: 'camionnette', label: 'Camionnette' },
  { key: 'en_intervention', label: 'En intervention' },
]

export const OUTIL_STATUTS = [
  { key: 'disponible', label: 'Disponible', color: '#16a34a' },
  { key: 'en_intervention', label: 'En intervention', color: '#2563eb' },
  { key: 'en_reparation', label: 'En réparation', color: '#a16207' },
  { key: 'perdu', label: 'Perdu', color: '#b91c1c' },
]

export const emplacementLabel = (key) =>
  OUTIL_EMPLACEMENTS.find(e => e.key === key)?.label ?? key ?? '—'

export const statutMeta = (key) =>
  OUTIL_STATUTS.find(s => s.key === key) ?? { key, label: key ?? '—', color: '#64748b' }

// Filtrage client-side (en plus du filtre serveur) — recherche libre.
export function filterOutillage(list, { search = '', emplacement = '', statut = '' } = {}) {
  const q = search.trim().toLowerCase()
  return (list ?? []).filter(o => {
    if (emplacement && o.emplacement !== emplacement) return false
    if (statut && o.statut !== statut) return false
    if (!q) return true
    return [o.nom, o.categorie, o.asset_tag, o.numero_serie]
      .some(v => (v ?? '').toLowerCase().includes(q))
  })
}
