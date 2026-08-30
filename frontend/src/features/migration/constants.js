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

/* NTMIG29 — miroir d'affichage de ``crm.Partenaire.NiveauCertification``
   (échelle croissante, cf. ``NIVEAUX_ORDONNES`` côté serveur). */
export const NIVEAUX_CERTIFICATION = [
  { value: '', label: 'Tous niveaux' },
  { value: 'aucun', label: 'Aucun' },
  { value: 'enregistre', label: 'Enregistré' },
  { value: 'certifie', label: 'Certifié' },
  { value: 'or', label: 'Or' },
  { value: 'platine', label: 'Platine' },
]

/* NTMIG29 — miroir d'affichage de ``crm.SPECIALITES_PARTENAIRE`` (liste
   FERMÉE des modules qu'un partenaire intégrateur peut déclarer). */
export const SPECIALITES_PARTENAIRE = [
  { value: '', label: 'Toutes spécialités' },
  { value: 'crm', label: 'CRM & prospection' },
  { value: 'ventes', label: 'Ventes & devis' },
  { value: 'compta', label: 'Comptabilité' },
  { value: 'stock', label: 'Stock & achats' },
  { value: 'installations', label: 'Chantiers & installations' },
  { value: 'sav', label: 'SAV & maintenance' },
  { value: 'rh', label: 'RH & paie' },
  { value: 'migration', label: 'Migration de données' },
]

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
