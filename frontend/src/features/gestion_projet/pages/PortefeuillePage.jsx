import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Wallet } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import { Card, Segmented } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { StatutProjet, STATUTS_PROJET, SanteRAG, errMessage } from '../constants'

/* AUDV16 (PROJ36/PROJ26) — Portefeuille : `tableau_portefeuille` était déjà
   câblé backend + client API (`gestionProjetApi.getPortefeuille`) mais ZÉRO
   écran ne l'appelait — le fondateur a tranché : construire l'écran (note
   « MENU FONDATEUR » d'AUD3, docs/PLAN.md). Le sélecteur a été vectorisé
   AVANT cet écran (GP-4, voir selectors.tableau_portefeuille) : le nombre de
   requêtes SQL ne dépend plus du nombre de projets. Donnée 100 % INTERNE
   (marge réelle, charge) — jamais exposée au client. */

const FILTERS = [{ value: '', label: 'Tous' }, ...STATUTS_PROJET]

export default function PortefeuillePage() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statut, setStatut] = useState('')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await gestionProjetApi.getPortefeuille(statut ? { statut } : undefined)
      setData(res.data ?? null)
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger le portefeuille.'))
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

  const rows = data?.projets ?? []

  const columns = useMemo(() => [
    { id: 'code', header: 'Code', width: 110,
      accessor: (p) => p.code,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'nom', header: 'Projet', width: 220,
      accessor: (p) => p.nom,
      cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'statut', header: 'Statut', width: 120,
      accessor: (p) => p.statut,
      cell: (v) => <StatutProjet status={v} /> },
    { id: 'avancement_pct', header: 'Avancement', align: 'right', width: 110,
      searchable: false, numeric: true,
      accessor: (p) => Number(p.avancement_pct ?? 0),
      cell: (v) => `${v}%` },
    { id: 'nb_retards', header: 'Retards', align: 'right', width: 90,
      searchable: false, numeric: true,
      accessor: (p) => Number(p.nb_retards ?? 0),
      cell: (v) => (v > 0
        ? <span className="font-semibold text-destructive">{v}</span>
        : v) },
    { id: 'nb_risques', header: 'À risque', align: 'right', width: 90,
      searchable: false, numeric: true,
      accessor: (p) => Number(p.nb_risques ?? 0),
      cell: (v) => (v > 0
        ? <span className="font-semibold text-warning">{v}</span>
        : v) },
    { id: 'derniere_sante', header: 'Santé', width: 100, searchable: false,
      accessor: (p) => p.derniere_sante,
      cell: (v) => (v
        ? <SanteRAG status={v} />
        : <span className="text-muted-foreground">—</span>) },
    { id: 'charge_totale', header: 'Charge (j-h)', align: 'right', width: 120,
      searchable: false, numeric: true,
      accessor: (p) => Number(p.charge_totale ?? 0) },
    { id: 'marge_reelle', header: 'Marge réelle', align: 'right', width: 140,
      searchable: false, numeric: true,
      accessor: (p) => Number(p.marge_reelle ?? 0),
      cell: (v, p) => (
        <span className={Number(p.marge_reelle) < 0 ? 'font-semibold text-destructive' : 'font-semibold'}>
          {formatMAD(p.marge_reelle)}
        </span>
      ) },
    { id: 'note_satisfaction', header: 'CSAT', align: 'right', width: 90,
      searchable: false,
      accessor: (p) => p.note_satisfaction ?? '',
      cell: (v) => (v !== '' && v != null ? v : <span className="text-muted-foreground">—</span>) },
  ], [])

  return (
    <ListShell
      title="Portefeuille"
      subtitle="Vue d'ensemble des projets — avancement, retards/risques, santé RAG et marge réelle. Donnée interne."
      filters={(
        <Segmented options={FILTERS} value={statut} onChange={setStatut}
                   aria-label="Filtrer par statut" />
      )}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchPlaceholder="Rechercher un projet (code, nom)…"
      exportName="portefeuille"
      onRowClick={(p) => navigate(`/projets/${p.projet_id}`)}
      emptyTitle="Aucun projet"
      emptyDescription="Le portefeuille se peuple automatiquement dès qu'un projet existe."
    >
      {data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted-foreground">Projets</span>
            <span className="text-lg font-semibold tabular-nums">{data.nb_projets}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted-foreground">Retards cumulés</span>
            <span className="text-lg font-semibold tabular-nums text-destructive">{data.total_retards}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted-foreground">À risque cumulés</span>
            <span className="text-lg font-semibold tabular-nums text-warning">{data.total_risques}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="text-xs text-muted-foreground">Charge cumulée (j-h)</span>
            <span className="text-lg font-semibold tabular-nums">{Number(data.total_charge ?? 0)}</span>
          </Card>
          <Card className="flex flex-col gap-1 p-3">
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Wallet className="size-3.5" aria-hidden="true" /> Marge réelle cumulée
            </span>
            <span className={`text-lg font-semibold tabular-nums ${Number(data.total_marge_reelle) < 0 ? 'text-destructive' : ''}`}>
              {formatMAD(data.total_marge_reelle)}
            </span>
          </Card>
        </div>
      )}
    </ListShell>
  )
}
