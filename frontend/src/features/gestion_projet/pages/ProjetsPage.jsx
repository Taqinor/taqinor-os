import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import { Button, Segmented, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { StatutProjet, STATUTS_PROJET, errMessage } from '../constants'
import ProjetFormDialog from '../components/ProjetFormDialog'

/* UX38 — Projets (liste + machine à états). Liste multi-chantier des projets ;
   clic → écran de détail avec transitions gardées, liens CRM/chantier, clôture. */

const FILTERS = [{ value: '', label: 'Tous' }, ...STATUTS_PROJET]

export default function ProjetsPage() {
  const navigate = useNavigate()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statut, setStatut] = useState('')
  const [showForm, setShowForm] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await gestionProjetApi.getProjets(statut ? { statut } : undefined)
      setRows(Array.isArray(res.data) ? res.data : res.data?.results ?? [])
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les projets.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statut])

  const columns = useMemo(() => [
    {
      id: 'code',
      header: 'Code',
      width: 120,
      accessor: (p) => p.code,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span>,
    },
    {
      id: 'nom',
      header: 'Projet',
      width: 260,
      accessor: (p) => p.nom,
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      accessor: (p) => p.statut,
      cell: (v) => <StatutProjet status={v} />,
    },
    {
      id: 'date_debut',
      header: 'Début',
      width: 120,
      searchable: false,
      accessor: (p) => p.date_debut ?? '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'date_fin_prevue',
      header: 'Fin prévue',
      width: 120,
      searchable: false,
      accessor: (p) => p.date_fin_prevue ?? '',
      cell: (v) => (v ? formatDate(v) : '—'),
    },
    {
      id: 'budget_total',
      header: 'Budget',
      align: 'right',
      numeric: true,
      width: 150,
      searchable: false,
      accessor: (p) => Number(p.budget_total ?? 0),
      cell: (_v, p) => (p.budget_total ? formatMAD(p.budget_total) : '—'),
    },
  ], [])

  return (
    <>
      <ListShell
        title="Projets"
        subtitle="Projets solaires multi-chantier — étude, appro, pose, mise en service, réception."
        actions={(
          <Button onClick={() => setShowForm(true)}>
            <Plus /> Nouveau projet
          </Button>
        )}
        filters={(
          <Segmented
            options={FILTERS}
            value={statut}
            onChange={setStatut}
            aria-label="Filtrer par statut"
          />
        )}
        columns={columns}
        rows={rows}
        loading={loading}
        error={error}
        searchPlaceholder="Rechercher un projet (code, nom)…"
        exportName="projets"
        onRowClick={(p) => navigate(`/projets/${p.id}`)}
        emptyTitle="Aucun projet"
        emptyDescription="Créez votre premier projet pour piloter un chantier."
        emptyAction={<Button size="sm" onClick={() => setShowForm(true)}><Plus className="size-4" /> Nouveau projet</Button>}
      />
      {showForm && (
        <ProjetFormDialog
          onClose={() => setShowForm(false)}
          onSaved={(created) => {
            setShowForm(false)
            toast.success('Projet créé.')
            if (created?.id) navigate(`/projets/${created.id}`)
            else load()
          }}
        />
      )}
    </>
  )
}
