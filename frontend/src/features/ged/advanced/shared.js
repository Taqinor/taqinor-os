/* ============================================================================
   UX45–UX47 — GED avancée : constantes, pastilles de statut et petits helpers
   partagés par les trois écrans (approbation, rétention, tags).
   ----------------------------------------------------------------------------
   Fichier .js PUR (aucun JSX) : les pastilles sont créées via `statusPill(map)`
   du kit UX1, qui renvoie un composant sans JSX écrit ici. Les libellés/tons
   des statuts backend (demandes d'approbation/signature) vivent ici, source de
   vérité unique pour les listes et les filtres.
   ========================================================================== */
import { statusPill } from '../../../ui/module'

/** Extrait un message d'erreur serveur lisible (jamais de JSON brut). */
export function errMessage(err, fallback = 'Une erreur est survenue — réessayez.') {
  const data = err?.response?.data
  if (typeof data === 'string' && data) return data
  if (data?.detail) return data.detail
  // Première erreur de champ (ex. { document: 'Document inconnu.' }).
  if (data && typeof data === 'object') {
    const first = Object.values(data)[0]
    if (Array.isArray(first) && first.length) return String(first[0])
    if (typeof first === 'string' && first) return first
  }
  return err?.detail ?? fallback
}

/** Formate une taille en octets en Ko/Mo/Go lisibles (jamais d'exception). */
export function formatOctets(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0) return '—'
  if (n === 0) return '0 o'
  const units = ['o', 'Ko', 'Mo', 'Go', 'To']
  const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)))
  const val = n / 1024 ** i
  return `${val.toLocaleString('fr-FR', { maximumFractionDigits: i === 0 ? 0 : 1 })} ${units[i]}`
}

// GED18 — statuts d'une demande d'approbation (backend : en_attente/approuve/rejete).
export const StatutApprobation = statusPill({
  en_attente: { label: 'En attente', tone: 'warning' },
  approuve: { label: 'Approuvée', tone: 'success' },
  rejete: { label: 'Rejetée', tone: 'danger' },
})

// GED30 — statuts d'une demande de signature (backend : en_attente/signe/annule/expire).
export const StatutSignature = statusPill({
  en_attente: { label: 'En attente', tone: 'warning' },
  signe: { label: 'Signée', tone: 'success' },
  annule: { label: 'Annulée', tone: 'neutral' },
  expire: { label: 'Expirée', tone: 'danger' },
})

// GED22 — action à l'échéance d'une politique de rétention.
export const ActionEcheance = statusPill({
  signaler: { label: 'Signaler', tone: 'info' },
  archiver: { label: 'Archiver', tone: 'warning' },
  supprimer: { label: 'Supprimer', tone: 'danger' },
})

// Cibles polymorphes autorisées pour un lien document↔objet métier (GED6).
// Alignées sur `records.ALLOWED_TARGETS` — libellés FR pour l'UI.
export const CIBLES_LIEN = [
  { value: 'crm.lead', label: 'Lead (CRM)' },
  { value: 'crm.client', label: 'Client' },
  { value: 'ventes.devis', label: 'Devis' },
  { value: 'ventes.facture', label: 'Facture' },
  { value: 'installations.chantier', label: 'Chantier' },
  { value: 'sav.ticket', label: 'Ticket SAV' },
]
