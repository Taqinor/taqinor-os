/* ============================================================================
   UX45–UX47 — GED avancée : constantes, pastilles de statut et petits helpers
   partagés par les trois écrans (approbation, rétention, tags).
   ----------------------------------------------------------------------------
   Fichier .js PUR (aucun JSX) : les pastilles sont créées via `statusPill(map)`
   du kit UX1, qui renvoie un composant sans JSX écrit ici. Les libellés/tons
   des statuts backend (demandes d'approbation/signature) vivent ici, source de
   vérité unique pour les listes et les filtres.
   ========================================================================== */
import { useEffect, useState } from 'react'
import { CheckCircle2, Trash2, XCircle } from 'lucide-react'
import { statusPill } from '../../../ui/module'
import { toast } from '../../../ui'
import { fetchAllPages } from '../../../utils/fetchAllPages'

/** ADOC31 — lit une liste GED paginée EN ENTIER (StandardPagination : 50 par
 *  défaut, 200 max) et renvoie une réponse `{ data: [...] }` (même forme
 *  qu'un appel axios, donc consommable tel quel par les écrans). Une liste
 *  non paginée (tableau brut) passe inchangée. */
export async function toutesLesPages(appel, params = {}) {
  const res = await fetchAllPages(
    (page) => appel({ ...params, page, page_size: 200 }).then((r) => r?.data))
  return { data: Array.isArray(res) ? res : (res?.results ?? []) }
}

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

/** Réponse DRF paginée ou tableau brut -> tableau. */
export function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

/** Résumé lisible de la 1re condition d'un groupe (`champ opérateur valeur`). */
export function resumeCondition(conditionGroup, operateurs) {
  const leaf = conditionGroup?.conditions?.[0]
  if (!leaf?.field) return '—'
  if (leaf.operator === 'exists') return `${leaf.field} existe`
  const val = Array.isArray(leaf.value) ? leaf.value.join(', ') : leaf.value
  const op = operateurs.find((o) => o.value === leaf.operator)?.label || leaf.operator
  return `${leaf.field} ${op} ${val ?? ''}`.trim()
}

/** Chargement d'un écran GED : `fetcher` lit et range les données ; l'état
 *  `loading`/`error` et la relecture `load` sont communs à tous les écrans. */
export function useChargementGed(fetcher, messageErreur) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      await fetcher()
    } catch (err) {
      setError(errMessage(err, messageErreur))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chargement au montage seulement
  }, [])

  return { loading, error, load }
}

/** Exécute une action serveur, confirme par un toast puis recharge. */
export async function actionAvecToast(action, messageSucces, recharger) {
  try { await action(); toast.success(messageSucces); recharger() }
  catch (err) { toast.error(errMessage(err)) }
}

/** Menu de ligne commun : activer/désactiver puis supprimer. */
export function actionsActivation(r, toggleActif, supprimer) {
  return [
    r.actif
      ? { id: 'desactiver', label: 'Désactiver', icon: XCircle, onClick: () => toggleActif(r) }
      : { id: 'activer', label: 'Activer', icon: CheckCircle2, onClick: () => toggleActif(r) },
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: () => supprimer(r),
    },
  ]
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
