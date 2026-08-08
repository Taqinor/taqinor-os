import { useEffect, useMemo, useState } from 'react'
import { Check, X } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Badge, toast } from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT84 — Guichet des demandes RH (attestations).
   ----------------------------------------------------------------------------
   `DemandeRH` (XRH9) est le guichet self-service d'attestations (travail /
   salaire / domiciliation) : l'employé demande déjà depuis le portail, cet
   écran donne à Administrateur/Responsable la file à traiter (`traiter`
   génère le PDF via le renderer paie existant) ou refuser. Un traitant sans
   `salaires_voir` reçoit le 403 SERVEUR affiché TEL QUEL — jamais un bouton
   masqué côté client (Done= de PACT84).
   ========================================================================== */

export default function DemandesRh() {
  const { confirmDelete } = useConfirmDialog()
  const [demandes, setDemandes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadTick, setReloadTick] = useState(0)

  const recharger = () => {
    setLoading(true)
    setError(null)
    setReloadTick((t) => t + 1)
  }

  useEffect(() => {
    let vivant = true
    rhApi.getDemandesRh()
      .then((res) => { if (vivant) setDemandes(unwrapList(res)) })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les demandes RH.')
        toast.error('Impossible de charger les demandes RH.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const traiter = async (d) => {
    try {
      await rhApi.traiterDemandeRh(d.id)
      toast.success('Demande traitée — attestation générée.')
      recharger()
    } catch (err) {
      // XRH9 — le 403 serveur (salaires_voir manquant) est relayé TEL QUEL.
      toast.error(err?.response?.data?.detail ?? 'Traitement impossible.')
    }
  }

  const refuser = async (d) => {
    const ok = await confirmDelete({
      title: 'Refuser cette demande RH ?',
      description: 'Le collaborateur en sera informé.',
      confirmLabel: 'Refuser',
    })
    if (!ok) return
    try {
      await rhApi.refuserDemandeRh(d.id, { motif_refus: 'Refusée par le responsable.' })
      toast.success('Demande refusée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Refus impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (d) => d.employe_nom || String(d.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: 'Type', width: 200, accessor: (d) => d.type_display || d.type || '', cell: (v) => v || '—' },
    { id: 'message', header: 'Message', width: 220, accessor: (d) => d.message || '', cell: (v) => v || '—' },
    { id: 'statut', header: 'Statut', width: 120, accessor: (d) => d.statut_display || d.statut || '', cell: (v, d) => <Badge tone={d.statut === 'traitee' ? 'success' : d.statut === 'refusee' ? 'danger' : 'neutral'}>{v || '—'}</Badge> },
    { id: 'cree', header: 'Soumise le', width: 130, searchable: false, accessor: (d) => d.date_creation || '', cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const rowActions = (d) => {
    if (d.statut !== 'soumise') return []
    return [
      { id: 'traiter', label: 'Traiter', icon: Check, onClick: () => traiter(d) },
      { id: 'refuser', label: 'Refuser', icon: X, destructive: true, onClick: () => refuser(d) },
    ]
  }

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Demandes RH (attestations)</h2>
      </div>

      <ListShell
        title="Guichet des demandes"
        columns={columns}
        rows={demandes}
        loading={loading}
        error={error}
        searchable
        exportName="demandes-rh"
        rowActions={rowActions}
        emptyTitle="Aucune demande"
        emptyDescription="Aucune demande RH en attente."
      />
    </div>
  )
}
