import { useEffect, useMemo, useState } from 'react'
import { Check, X } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Card, Stat, Badge, toast } from '../../ui'
import { useConfirmDialog } from '../../ui/confirm'
import { formatDate, formatNumber } from '../../lib/format'
import { unwrapList } from '../../api/resource'
import rhApi from '../../api/rhApi'

/* ============================================================================
   PACT83 — Demandes d'allocation de congés.
   ----------------------------------------------------------------------------
   `DemandeAllocation` (ZRH13) permet de demander une allocation EXCEPTIONNELLE
   de jours (RTT, ancienneté, don de jours), distincte d'une demande de congé
   classique — validée, elle crédite `SoldeConge.acquis` via
   `services.valider_allocation`. Le solde affiché ici vient TOUJOURS de la
   réponse serveur (`rhApi.getSoldesConge`), jamais recalculé côté client.
   ========================================================================== */

export default function DemandesAllocation() {
  const { confirmDelete } = useConfirmDialog()
  const [demandes, setDemandes] = useState([])
  const [soldes, setSoldes] = useState([])
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
    Promise.all([rhApi.getDemandesAllocation(), rhApi.getSoldesConge()])
      .then(([d, s]) => {
        if (!vivant) return
        setDemandes(unwrapList(d))
        setSoldes(unwrapList(s))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les demandes d’allocation.')
        toast.error('Impossible de charger les demandes d’allocation.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }, [reloadTick])

  const valider = async (d) => {
    try {
      await rhApi.validerDemandeAllocation(d.id)
      toast.success('Demande validée — solde crédité.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  const refuser = async (d) => {
    const ok = await confirmDelete({
      title: 'Refuser cette demande d’allocation ?',
      description: 'Aucun crédit de solde ne sera appliqué.',
      confirmLabel: 'Refuser',
    })
    if (!ok) return
    try {
      await rhApi.refuserDemandeAllocation(d.id)
      toast.success('Demande refusée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Refus impossible.')
    }
  }

  const columns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (d) => d.employe_nom || String(d.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'type', header: 'Type', width: 140, accessor: (d) => d.type_absence_code || String(d.type_absence || ''), cell: (v) => v || '—' },
    { id: 'jours', header: 'Jours', width: 90, align: 'right', numeric: true, searchable: false, accessor: (d) => Number(d.jours ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
    { id: 'motif', header: 'Motif', width: 220, accessor: (d) => d.motif || '', cell: (v) => v || '—' },
    { id: 'statut', header: 'Statut', width: 120, accessor: (d) => d.statut_display || d.statut || '', cell: (v, d) => <Badge tone={d.statut === 'validee' ? 'success' : d.statut === 'refusee' ? 'danger' : 'neutral'}>{v || '—'}</Badge> },
    { id: 'cree', header: 'Soumise le', width: 130, searchable: false, accessor: (d) => d.date_creation || '', cell: (v) => (v ? formatDate(v) : '—') },
  ], [])

  const rowActions = (d) => {
    if (d.statut !== 'soumise') return []
    return [
      { id: 'valider', label: 'Valider', icon: Check, onClick: () => valider(d) },
      { id: 'refuser', label: 'Refuser', icon: X, destructive: true, onClick: () => refuser(d) },
    ]
  }

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Demandes d’allocation de congés</h2>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <ListShell
          title="Demandes"
          columns={columns}
          rows={demandes}
          loading={loading}
          error={error}
          searchable
          exportName="demandes-allocation"
          rowActions={rowActions}
          emptyTitle="Aucune demande"
          emptyDescription="Aucune demande d’allocation en attente."
        />

        <div className="flex flex-col gap-3">
          <h3 className="text-sm font-medium text-muted-foreground">Soldes de congés</h3>
          {loading ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : soldes.length === 0 ? (
            <Card className="p-4 text-sm text-muted-foreground">Aucun solde.</Card>
          ) : (
            soldes.map((s) => (
              <Card key={s.id} className="p-4">
                <p className="mb-2 text-sm font-medium">
                  {s.employe_nom || `Employé ${s.employe}`} · {s.annee}
                </p>
                <Stat
                  label="Disponible"
                  value={`${formatNumber(s.disponible ?? 0, { decimals: 1 })} j`}
                  hint={`${formatNumber(s.acquis ?? 0, { decimals: 1 })} acquis`}
                />
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
