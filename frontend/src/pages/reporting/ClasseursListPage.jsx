import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sheet, Plus, Trash2 } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import {
  Button, DataTable, EmptyState, IconButton, Input, Spinner,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog, toast } from '../../ui/confirm'

/* XPLT22 — Liste des classeurs (mini-spreadsheet BI) : création + navigation
   vers la grille (`ClasseurPage`, `/reporting/classeurs/:id`). */

export default function ClasseursListPage() {
  const navigate = useNavigate()
  const { confirmDelete } = useConfirmDialog()
  const [classeurs, setClasseurs] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [titre, setTitre] = useState('')
  const [creating, setCreating] = useState(false)

  const reload = () => reportingApi.listClasseurs()
    .then((r) => setClasseurs(r.data?.results ?? r.data ?? []))
    .catch(() => setClasseurs([]))

  useEffect(() => {
    let active = true
    reportingApi.listClasseurs()
      .then((r) => { if (active) setClasseurs(r.data?.results ?? r.data ?? []) })
      .catch(() => { if (active) setClasseurs([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const creer = (e) => {
    e.preventDefault()
    setCreating(true)
    reportingApi.createClasseur({ titre, cellules: {}, liens: {} })
      .then((r) => {
        toast.success('Classeur créé.')
        setDialogOpen(false)
        setTitre('')
        navigate(`/reporting/classeurs/${r.data.id}`)
      })
      .catch(() => toast.error('Création impossible.'))
      .finally(() => setCreating(false))
  }

  const remove = async (classeur) => {
    const ok = await confirmDelete({
      title: 'Supprimer ce classeur ?',
      description: `Le classeur « ${classeur.titre} » sera supprimé.`,
    })
    if (!ok) return
    reportingApi.deleteClasseur(classeur.id)
      .then(() => { toast.success('Classeur supprimé.'); reload() })
      .catch(() => toast.error('Suppression impossible.'))
  }

  const columns = useMemo(() => [
    { id: 'titre', header: 'Titre', accessor: (r) => r.titre },
    {
      id: 'partage', header: 'Partagé', width: 100,
      accessor: (r) => (r.partage ? 'Oui' : 'Non'),
    },
    {
      id: 'actions', header: '', width: 100, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <IconButton variant="ghost" label="Supprimer" onClick={() => remove(r)}>
          <Trash2 />
        </IconButton>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- remove recréé par rendu
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Classeurs</h1>
        <div className="page-subtitle">Mini-tableurs BI avec données live et formules.</div>
      </div>

      <div className="mb-4 flex justify-end">
        <Button onClick={() => setDialogOpen(true)}><Plus /> Nouveau classeur</Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : classeurs.length === 0 ? (
        <EmptyState
          icon={Sheet}
          title="Aucun classeur"
          description="Créez un classeur pour construire un mini-tableau de bord avec formules."
          className="my-6"
        />
      ) : (
        <DataTable
          data={classeurs}
          columns={columns}
          getRowId={(row) => row.id}
          onRowClick={(row) => navigate(`/reporting/classeurs/${row.id}`)}
          searchable={false}
          pageSize={25}
          aria-label="Classeurs"
        />
      )}

      <ResponsiveDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title="Nouveau classeur"
      >
        <form onSubmit={creer} noValidate className="flex flex-col gap-3">
          <Input
            placeholder="Titre du classeur"
            value={titre}
            onChange={(e) => setTitre(e.target.value)}
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={creating} disabled={!titre.trim()}>Créer</Button>
          </div>
        </form>
      </ResponsiveDialog>
    </div>
  )
}
