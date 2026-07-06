import { useCallback, useEffect, useMemo, useState } from 'react'
import { ListChecks } from 'lucide-react'
import {
  Card, Button, Spinner, EmptyState, Badge, DataTable, Segmented, toast,
} from '../../../ui'
import { formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import {
  errMessage, StatutTache, PrioriteTache, STATUTS_TACHE, PRIORITES_TACHE,
} from '../constants'
import ProjetPicker from '../components/ProjetPicker'
import TachesKanbanView from '../components/TachesKanbanView'
import ChronoButton from '../components/ChronoWidget'

/* XPRJ10-12 — Écran transverse des tâches (toutes tâches de la société,
   filtrables par projet/assigné/priorité/statut), avec bascule liste/kanban.
   Le drag kanban PATCH le statut (même optimistic update + rollback que dans
   ProjetDetailPage). Distinct de « Mes tâches » (mes-taches, transverse aux
   projets pour l'utilisateur courant) — voir TachesPage avec mesTaches=true. */

const VUE_OPTIONS = [
  { value: 'liste', label: 'Liste' },
  { value: 'kanban', label: 'Kanban' },
]

export default function TachesPage({ mesTaches = false }) {
  const [projetId, setProjetId] = useState('')
  const [ressourceId, setRessourceId] = useState('')
  const [priorite, setPriorite] = useState('')
  const [statut, setStatut] = useState('')
  const [ressources, setRessources] = useState([])
  const [taches, setTaches] = useState([])
  const [vue, setVue] = useState('liste')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyTacheId, setBusyTacheId] = useState(null)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      if (mesTaches) {
        const res = await gestionProjetApi.getMesTaches()
        setTaches(Array.isArray(res.data) ? res.data : [])
      } else {
        const params = {}
        if (projetId) params.projet = projetId
        if (ressourceId) params.assigne = ressourceId
        if (priorite) params.priorite = priorite
        if (statut) params.statut = statut
        const [t, r] = await Promise.all([
          gestionProjetApi.getTaches(params),
          gestionProjetApi.getRessources(),
        ])
        setTaches(asList(t))
        setRessources(asList(r))
      }
    } catch (err) {
      setError(errMessage(err, 'Chargement des tâches impossible.'))
    } finally {
      setLoading(false)
    }
  }, [mesTaches, projetId, ressourceId, priorite, statut])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    return () => { alive = false }
  }, [load])

  const changeStatutTache = async (tache, nouveauStatut) => {
    if (!tache || tache.statut === nouveauStatut) return
    const ancien = tache.statut
    setBusyTacheId(tache.id)
    setTaches((rows) => rows.map((t) => (t.id === tache.id ? { ...t, statut: nouveauStatut } : t)))
    try {
      await gestionProjetApi.updateTache(tache.id, { statut: nouveauStatut })
    } catch (err) {
      setTaches((rows) => rows.map((t) => (t.id === tache.id ? { ...t, statut: ancien } : t)))
      toast.error(errMessage(err, "Le changement de statut n'a pas pu être enregistré — réessayez."))
    } finally {
      setBusyTacheId(null)
    }
  }

  const columns = useMemo(() => [
    { id: 'code', header: 'Code', width: 90, searchable: false, accessor: (t) => t.code_wbs || '', cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'libelle', header: 'Tâche', accessor: (t) => t.libelle, cell: (v) => <span className="font-medium">{v}</span> },
    { id: 'projet', header: 'Projet', accessor: (t) => t.projet_code || `#${t.projet}` },
    { id: 'assigne', header: 'Assigné', accessor: (t) => t.assigne_nom || '—' },
    { id: 'priorite', header: 'Priorité', searchable: false, accessor: (t) => t.priorite, cell: (v) => <PrioriteTache status={v} /> },
    { id: 'statut', header: 'Statut', searchable: false, accessor: (t) => t.statut, cell: (v) => <StatutTache status={v} /> },
    { id: 'echeance', header: 'Échéance', searchable: false, accessor: (t) => t.date_fin_prevue || '', cell: (v) => v ? formatDate(v) : '—' },
    { id: 'chrono', header: 'Chrono', searchable: false, sortable: false, accessor: () => null, cell: (_v, t) => <ChronoButton tache={t} /> },
  ], [])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">
            {mesTaches ? 'Mes tâches' : 'Tâches'}
          </h1>
          <p className="text-sm text-muted-foreground">
            {mesTaches
              ? 'Vos tâches non terminées, tous projets confondus, triées par urgence.'
              : 'Toutes les tâches, filtrables par projet, assigné, priorité et statut.'}
          </p>
        </div>
        <Segmented options={VUE_OPTIONS} value={vue} onChange={setVue} aria-label="Vue" />
      </div>

      {!mesTaches && (
        <Card className="flex flex-wrap items-end gap-3 p-3">
          <ProjetPicker value={projetId} onChange={setProjetId} />
          <select
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm"
            value={ressourceId}
            onChange={(e) => setRessourceId(e.target.value)}
            aria-label="Filtrer par assigné"
          >
            <option value="">Tous les assignés</option>
            {ressources.map((r) => <option key={r.id} value={r.id}>{r.nom}</option>)}
          </select>
          <select
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm"
            value={priorite}
            onChange={(e) => setPriorite(e.target.value)}
            aria-label="Filtrer par priorité"
          >
            <option value="">Toutes priorités</option>
            {PRIORITES_TACHE.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <select
            className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm"
            value={statut}
            onChange={(e) => setStatut(e.target.value)}
            aria-label="Filtrer par statut"
          >
            <option value="">Tous statuts</option>
            {STATUTS_TACHE.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={load}>Réessayer</Button>} />
      ) : taches.length === 0 ? (
        <EmptyState icon={ListChecks} title="Aucune tâche" description={mesTaches ? "Vous n'avez aucune tâche assignée." : 'Aucune tâche ne correspond à ces filtres.'} />
      ) : vue === 'kanban' ? (
        <TachesKanbanView taches={taches} onChangeStatut={changeStatutTache} busyTacheId={busyTacheId} />
      ) : (
        <Card className="p-4 sm:p-5">
          <DataTable
            data={taches}
            getRowId={(t) => t.id}
            columns={columns}
            exportName="taches"
            emptyTitle="Aucune tâche"
            emptyDescription="Aucune tâche ne correspond à ces filtres."
          />
        </Card>
      )}
    </div>
  )
}
