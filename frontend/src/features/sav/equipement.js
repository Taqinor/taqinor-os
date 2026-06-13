// Parc d'équipements — libellés, états de garantie, filtres et tri.
// L'état de garantie est calculé côté serveur (champ `garantie_etat`) ; on en
// garde ici les libellés/couleurs et un repli local de cohérence.

export const EQUIP_STATUTS = [
  { value: 'en_service', label: 'En service' },
  { value: 'remplace', label: 'Remplacé' },
  { value: 'hors_service', label: 'Hors service' },
]

export const EQUIP_STATUT_LABELS = {
  en_service: 'En service',
  remplace: 'Remplacé',
  hors_service: 'Hors service',
}

// États de garantie (alignés sur le serializer backend `garantie_etat`).
export const GARANTIE_ETATS = {
  sous_garantie: { label: 'Sous garantie', color: '#16a34a' },
  expire_bientot: { label: 'Expire bientôt', color: '#f59e0b' },
  hors_garantie: { label: 'Hors garantie', color: '#dc2626' },
  non_renseignee: { label: 'Garantie non renseignée', color: '#64748b' },
}

export const GARANTIE_FILTRES = [
  { value: '', label: 'Toutes garanties' },
  { value: 'sous_garantie', label: 'Sous garantie' },
  { value: 'expire_bientot', label: 'Expire bientôt (≤ 90 j)' },
  { value: 'hors_garantie', label: 'Hors garantie' },
  { value: 'non_renseignee', label: 'Non renseignée' },
]

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// Texte d'indicateur de garantie clair pour un équipement.
export function garantieLabel(eq) {
  const etat = eq?.garantie_etat ?? 'non_renseignee'
  if (etat === 'non_renseignee') return 'Garantie non renseignée'
  if (etat === 'hors_garantie') return 'Hors garantie'
  const jours = eq?.garantie_jours_restants
  if (etat === 'expire_bientot' && typeof jours === 'number') {
    return `Expire dans ${jours} j (le ${formatDateFR(eq.date_fin_garantie)})`
  }
  return `Sous garantie jusqu'au ${formatDateFR(eq?.date_fin_garantie)}`
}

export function garantieColor(eq) {
  return (GARANTIE_ETATS[eq?.garantie_etat] ?? GARANTIE_ETATS.non_renseignee).color
}

export const EMPTY_EQUIP_FILTERS = {
  q: '',
  produit: '',
  marque: '',
  garantie: '',
  statut: '',
}

export function filterEquipements(items, filters) {
  const f = { ...EMPTY_EQUIP_FILTERS, ...(filters ?? {}) }
  const q = f.q.trim().toLowerCase()
  return (items ?? []).filter((it) => {
    if (f.produit && String(it.produit) !== String(f.produit)) return false
    if (f.marque && (it.produit_marque ?? '').toLowerCase() !== f.marque.toLowerCase()) return false
    if (f.garantie && (it.garantie_etat ?? 'non_renseignee') !== f.garantie) return false
    if (f.statut && it.statut !== f.statut) return false
    if (!q) return true
    return (
      (it.numero_serie ?? '').toLowerCase().includes(q) ||
      (it.produit_nom ?? '').toLowerCase().includes(q) ||
      (it.produit_marque ?? '').toLowerCase().includes(q) ||
      (it.installation_reference ?? '').toLowerCase().includes(q) ||
      (it.client_nom ?? '').toLowerCase().includes(q)
    )
  })
}

// Tri : par défaut par date de fin de garantie (les vides en fin).
export function sortEquipements(items, key, dir) {
  const sign = dir === 'asc' ? 1 : -1
  const arr = [...(items ?? [])]
  const EMPTY = dir === 'asc' ? '9999-99-99' : ''
  arr.sort((a, b) => {
    let va
    let vb
    if (key === 'date_fin_garantie') {
      va = a.date_fin_garantie ?? EMPTY
      vb = b.date_fin_garantie ?? EMPTY
    } else {
      va = a[key] ?? ''
      vb = b[key] ?? ''
    }
    if (va < vb) return -1 * sign
    if (va > vb) return 1 * sign
    return 0
  })
  return arr
}
