// Modes de paiement (valeurs = Paiement.Mode côté serveur) — une seule liste
// partagée par la modale d'encaissement et « Facturer » un devis.
export const MODES_PAIEMENT = [
  { value: 'especes',     label: 'Espèces' },
  { value: 'virement',    label: 'Virement' },
  { value: 'cheque',      label: 'Chèque' },
  { value: 'carte',       label: 'Carte' },
  { value: 'prelevement', label: 'Prélèvement' },
  { value: 'autre',       label: 'Autre' },
]
