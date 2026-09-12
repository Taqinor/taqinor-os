import { statusPill } from '../../ui/module'

/* ============================================================================
   NTJUR — Taxonomies du module Affaires juridiques.
   ----------------------------------------------------------------------------
   Miroirs 1:1 des ``TextChoices`` backend (``DossierJuridique.Statut``,
   ``.Nature``, ``.TypeProcedure``, ``.NiveauConfidentialite``,
   ``MandatAvocat.Statut``, ``NoteHonoraires.Statut``, ``Audience.Statut``).
   Aucune valeur de statut n'est écrite en dur ailleurs dans le module.

   La machine à états N'EST PAS dupliquée ici : les transitions légales sont
   demandées au serveur (``statuts-suivants``), seule source de vérité — un
   miroir client finirait par diverger et proposerait un bouton qui échoue.
   ========================================================================== */

export const STATUT_MAP = {
  ouvert: { label: 'Ouvert', tone: 'info' },
  instruction: { label: 'En instruction', tone: 'info' },
  audience_programmee: { label: 'Audience programmée', tone: 'warning' },
  en_delibere: { label: 'En délibéré', tone: 'warning' },
  jugement_rendu: { label: 'Jugement rendu', tone: 'warning' },
  appel: { label: 'En appel', tone: 'warning' },
  execution: { label: 'En exécution', tone: 'info' },
  clos_gagne: { label: 'Clos — gagné', tone: 'success' },
  clos_perdu: { label: 'Clos — perdu', tone: 'danger' },
  clos_transaction: { label: 'Clos — transaction', tone: 'neutral' },
  clos_desistement: { label: 'Clos — désistement', tone: 'neutral' },
}

export const STATUTS_CLOS = [
  'clos_gagne', 'clos_perdu', 'clos_transaction', 'clos_desistement',
]

export const NATURE_MAP = {
  contentieux: 'Contentieux',
  precontentieux: 'Précontentieux',
  consultatif: 'Consultatif',
  recouvrement: 'Recouvrement',
}

export const PROCEDURE_MAP = {
  civil: 'Civil',
  commercial: 'Commercial',
  social: 'Social',
  penal: 'Pénal',
  administratif: 'Administratif',
  arbitrage: 'Arbitrage',
}

export const CONFIDENTIALITE_MAP = {
  public: { label: 'Public', tone: 'neutral' },
  interne: { label: 'Interne', tone: 'info' },
  confidentiel: { label: 'Confidentiel', tone: 'danger' },
}

export const POSITION_MAP = {
  demandeur: 'Demandeur',
  defendeur: 'Défendeur',
}

export const MANDAT_STATUT_MAP = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  en_approbation: { label: "En attente d'approbation", tone: 'warning' },
  actif: { label: 'Actif', tone: 'success' },
  clos: { label: 'Clos', tone: 'neutral' },
}

export const NOTE_STATUT_MAP = {
  recue: { label: 'Reçue', tone: 'neutral' },
  validee: { label: 'Validée', tone: 'info' },
  payee: { label: 'Payée', tone: 'success' },
}

export const AUDIENCE_STATUT_MAP = {
  programmee: { label: 'Programmée', tone: 'info' },
  tenue: { label: 'Tenue', tone: 'success' },
  reportee: { label: 'Reportée', tone: 'warning' },
  annulee: { label: 'Annulée', tone: 'neutral' },
}

export const StatutDossierPill = statusPill(STATUT_MAP)
export const ConfidentialitePill = statusPill(CONFIDENTIALITE_MAP)
export const StatutMandatPill = statusPill(MANDAT_STATUT_MAP)
export const StatutNotePill = statusPill(NOTE_STATUT_MAP)
export const StatutAudiencePill = statusPill(AUDIENCE_STATUT_MAP)

/** True si le dossier a atteint un statut terminal ``clos_*``. */
export function estClos(statut) {
  return STATUTS_CLOS.includes(statut)
}

export function labelStatut(v) {
  return STATUT_MAP[v]?.label ?? v ?? '—'
}
