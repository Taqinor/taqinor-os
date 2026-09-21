import { statusPill } from '../../ui/module'

/* ============================================================================
   FLOTTE — pastilles de statut par taxonomie (fabriquées via statusPill).
   ----------------------------------------------------------------------------
   Chaque famille de statut flotte (véhicule, réservation, entretien, OR,
   conformité réglementaire, sinistre, infraction, demande de pool) a sa Pill
   dédiée. `Pill.options` alimente les filtres <Select> ; `Pill.toneOf` sert aux
   colonnes. Tons réutilisés du thème (jamais la couleur comme seul signal — le
   libellé accompagne toujours).
   ========================================================================== */

export const VehiculeStatutPill = statusPill({
  actif: { label: 'Actif', tone: 'success' },
  maintenance: { label: 'En maintenance', tone: 'warning' },
  reforme: { label: 'Réformé', tone: 'neutral' },
  // XFLT4 — cycle de vie complet (acquisition → cession).
  commande: { label: 'Commandé', tone: 'info' },
  a_vendre: { label: 'À vendre', tone: 'warning' },
  vendu: { label: 'Vendu', tone: 'neutral' },
})

export const ReservationStatutPill = statusPill({
  demandee: { label: 'Demandée', tone: 'info' },
  confirmee: { label: 'Confirmée', tone: 'success' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

export const EntretienStatutPill = statusPill({
  a_faire: { label: 'À faire', tone: 'warning' },
  planifie: { label: 'Planifié', tone: 'info' },
  fait: { label: 'Fait', tone: 'success' },
})

export const OrStatutPill = statusPill({
  ouvert: { label: 'Ouvert', tone: 'warning' },
  // XFLT19 — chaîne d'approbation des devis de réparation externe.
  devis_recu: { label: 'Devis reçu', tone: 'info' },
  approuve: { label: 'Approuvé', tone: 'info' },
  en_cours: { label: 'En cours', tone: 'info' },
  cloture: { label: 'Clôturé', tone: 'success' },
})

// Statut réglementaire commun (échéances / assurances / VT / cartes grises).
export const ConformiteStatutPill = statusPill({
  a_jour: { label: 'À jour', tone: 'success' },
  valide: { label: 'Valide', tone: 'success' },
  a_renouveler: { label: 'À renouveler', tone: 'warning' },
  expire: { label: 'Expiré', tone: 'danger' },
  expiree: { label: 'Expirée', tone: 'danger' },
})

export const SinistreStatutPill = statusPill({
  declare: { label: 'Déclaré', tone: 'warning' },
  en_cours: { label: 'En cours', tone: 'info' },
  clos: { label: 'Clos', tone: 'neutral' },
  indemnise: { label: 'Indemnisé', tone: 'success' },
})

export const InfractionStatutPill = statusPill({
  a_payer: { label: 'À payer', tone: 'danger' },
  payee: { label: 'Payée', tone: 'success' },
  contestee: { label: 'Contestée', tone: 'warning' },
  classee: { label: 'Classée', tone: 'neutral' },
})

export const DemandeStatutPill = statusPill({
  demandee: { label: 'Demandée', tone: 'info' },
  approuvee: { label: 'Approuvée', tone: 'success' },
  refusee: { label: 'Refusée', tone: 'danger' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// XFLT5 — signalements d'anomalie véhicule (conducteur → OR).
export const SignalementStatutPill = statusPill({
  ouvert: { label: 'Ouvert', tone: 'warning' },
  en_cours: { label: 'En cours', tone: 'info' },
  resolu: { label: 'Résolu', tone: 'success' },
  clos: { label: 'Clos', tone: 'neutral' },
})

export const SignalementGravitePill = statusPill({
  faible: { label: 'Faible', tone: 'neutral' },
  moyenne: { label: 'Moyenne', tone: 'warning' },
  critique: { label: 'Critique', tone: 'danger' },
})
