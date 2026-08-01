/* Constantes partagées des écrans Migration ERP (NTMIG16/17). */

export const SOURCES = [
  { value: 'odoo', label: 'Odoo' },
  { value: 'sage', label: 'Sage' },
  { value: 'excel', label: 'Excel' },
  { value: 'csv_generique', label: 'CSV générique' },
]

export const STATUTS_PROJET = {
  brouillon: 'Brouillon',
  analyse: 'Analyse',
  chargement: 'Chargement',
  reconciliation: 'Réconciliation',
  termine: 'Terminé',
  echoue: 'Échoué',
}

export const STATUTS_LOT = {
  en_attente: 'En attente',
  analyse: 'Analysé',
  charge: 'Chargé',
  reconcilie: 'Réconcilié',
  echoue: 'Échoué',
}

/* Entités migrables — miroir des cibles d'import du moteur dataimport. */
export const ENTITES = [
  { value: 'clients', label: 'Clients' },
  { value: 'leads', label: 'Prospects (leads)' },
  { value: 'products', label: 'Produits' },
  { value: 'fournisseurs', label: 'Fournisseurs' },
  { value: 'equipements', label: 'Équipements' },
  { value: 'vehicules', label: 'Véhicules' },
]

export function labelSource(value) {
  return SOURCES.find((s) => s.value === value)?.label || value || '—'
}

/** Message d'erreur lisible depuis une erreur axios (jamais « [object Object] »). */
export function errMessage(err, repli) {
  const data = err?.response?.data
  if (typeof data === 'string' && data) return data
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail) && data.detail.length) {
    return String(data.detail[0])
  }
  if (data && typeof data === 'object') {
    const premier = Object.values(data).find(
      (v) => typeof v === 'string' || Array.isArray(v))
    if (typeof premier === 'string') return premier
    if (Array.isArray(premier) && premier.length) return String(premier[0])
  }
  return repli
}
