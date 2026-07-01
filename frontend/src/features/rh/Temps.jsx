import { useEffect, useMemo, useState } from 'react'
import { LogOut } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Segmented, Button, toast } from '../../ui'
import { formatNumber, formatDate, formatDateTime } from '../../lib/format'
import rhApi from '../../api/rhApi'

/* ============================================================================
   UX24 — Temps & présence.
   ----------------------------------------------------------------------------
   Vues : Pointages (arrivée/départ), Roster (affectations d'équipe), Présences
   chantier, Heures supplémentaires. Le pointage départ passe par l'@action
   serveur (durée calculée côté serveur). Export paie déclenché depuis la barre
   d'actions.
   ========================================================================== */

const VUES = [
  { value: 'pointages', label: 'Pointages' },
  { value: 'roster', label: 'Roster' },
  { value: 'presences', label: 'Présences chantier' },
  { value: 'heures_supp', label: 'Heures supp.' },
]

export default function Temps() {
  const [vue, setVue] = useState('pointages')
  const [pointages, setPointages] = useState([])
  const [roster, setRoster] = useState([])
  const [presences, setPresences] = useState([])
  const [heuresSupp, setHeuresSupp] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getPointages(),
      rhApi.getRoster(),
      rhApi.getPresencesChantier(),
      rhApi.getHeuresSupp(),
    ])
      .then(([pRes, rRes, prRes, hRes]) => {
        if (!vivant) return
        setPointages(unwrap(pRes.data))
        setRoster(unwrap(rRes.data))
        setPresences(unwrap(prRes.data))
        setHeuresSupp(unwrap(hRes.data))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger les temps & présences.')
        toast.error('Impossible de charger les temps & présences.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(recharger, [])

  const pointerDepart = async (p) => {
    try {
      await rhApi.pointagerDepart(p.id)
      toast.success('Départ pointé.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Pointage impossible.')
    }
  }

  const exporterPaie = async () => {
    try {
      const res = await rhApi.exportPaiePointages()
      const n = Array.isArray(res.data) ? res.data.length : (res.data?.results?.length ?? 0)
      toast.success(`Export paie prêt : ${n} ligne(s).`)
    } catch {
      toast.error('Export paie indisponible.')
    }
  }

  const pointageColumns = useMemo(() => [
    {
      id: 'employe',
      header: 'Employé',
      width: 180,
      accessor: (p) => p.employe_nom || String(p.employe || ''),
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'arrivee',
      header: 'Arrivée',
      width: 160,
      searchable: false,
      accessor: (p) => p.heure_arrivee || '',
      cell: (v) => (v ? formatDateTime(v) : '—'),
    },
    {
      id: 'depart',
      header: 'Départ',
      width: 160,
      searchable: false,
      accessor: (p) => p.heure_depart || '',
      cell: (v) => (v ? formatDateTime(v) : '—'),
    },
    {
      id: 'duree',
      header: 'Durée',
      width: 100,
      align: 'right',
      searchable: false,
      accessor: (p) => Number(p.duree_minutes ?? 0),
      cell: (v) => (v ? `${formatNumber(v / 60, { decimals: 1 })} h` : '—'),
    },
    {
      id: 'type',
      header: 'Type',
      width: 110,
      accessor: (p) => p.type_pointage_display || p.type_pointage || '',
      cell: (v) => v || '—',
    },
  ], [])

  const pointageActions = (p) => (p.heure_arrivee && !p.heure_depart
    ? [{ id: 'depart', label: 'Pointer le départ', icon: LogOut, onClick: () => pointerDepart(p) }]
    : [])

  const rosterColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (r) => r.employe_nom || String(r.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'equipe', header: 'Équipe', width: 140, accessor: (r) => r.equipe || '', cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (r) => r.date || '', cell: (v) => formatDate(v) },
    { id: 'creneau', header: 'Créneau', width: 120, accessor: (r) => r.creneau_display || r.creneau || '', cell: (v) => v || '—' },
  ], [])

  const presenceColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (p) => p.employe_nom || String(p.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'chantier', header: 'Chantier', width: 140, accessor: (p) => String(p.installation_id ?? ''), cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (p) => p.date || '', cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', width: 130, accessor: (p) => p.statut_display || p.statut || '', cell: (v) => v || '—' },
  ], [])

  const heuresColumns = useMemo(() => [
    { id: 'employe', header: 'Employé', width: 180, accessor: (h) => h.employe_nom || String(h.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (h) => h.date || '', cell: (v) => formatDate(v) },
    { id: 'total_hs', header: 'Total HS', width: 100, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.total_hs ?? 0), cell: (v) => `${formatNumber(v, { decimals: 1 })} h` },
    { id: 'hs_25', header: 'HS 25%', width: 90, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.hs_25 ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
    { id: 'hs_50', header: 'HS 50%', width: 90, align: 'right', numeric: true, searchable: false, accessor: (h) => Number(h.hs_50 ?? 0), cell: (v) => formatNumber(v, { decimals: 1 }) },
  ], [])

  const config = {
    pointages: { title: 'Pointages', columns: pointageColumns, rows: pointages, rowActions: pointageActions, exportName: 'pointages',
      actions: <Button variant="outline" onClick={exporterPaie}>Export paie</Button> },
    roster: { title: 'Roster', columns: rosterColumns, rows: roster, exportName: 'roster' },
    presences: { title: 'Présences chantier', columns: presenceColumns, rows: presences, exportName: 'presences-chantier' },
    heures_supp: { title: 'Heures supplémentaires', columns: heuresColumns, rows: heuresSupp, exportName: 'heures-supp' },
  }[vue]

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Temps & présence</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue temps & présence" />

      <ListShell
        title={config.title}
        columns={config.columns}
        rows={config.rows}
        loading={loading}
        error={error}
        searchable
        rowActions={config.rowActions}
        actions={config.actions}
        exportName={config.exportName}
        emptyTitle="Aucune ligne"
        emptyDescription="Aucune donnée pour cette vue."
      />
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}
