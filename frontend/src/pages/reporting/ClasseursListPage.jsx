import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sheet, Plus } from 'lucide-react'
import { colonneSupprimer } from './colonneSupprimer'
import reportingApi from '../../api/reportingApi'
import fetchAllPages from '../../utils/fetchAllPages'
import {
  Button, DataTable, EmptyState, Input,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog, toast } from '../../ui/confirm'
import { ChargementPage } from '../../ui/ChargementPage'

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

  const listerTous = () => fetchAllPages((page, { page_size: pageSize } = {}) =>
    reportingApi.listClasseurs({ page, page_size: pageSize }).then((r) => r.data))

  // AERR130 — une relecture en échec GARDE la liste affichée (jamais « Aucun
  // classeur ») et le dit : avis « Liste pas à jour » + Réessayer.
  const [pasAJour, setPasAJour] = useState(false)
  const reload = () => listerTous()
    .then((rows) => { setClasseurs(Array.isArray(rows) ? rows : (rows?.results ?? [])); setPasAJour(false) })
    .catch(() => setPasAJour(true))

  useEffect(() => {
    let active = true
    listerTous()
      .then((rows) => { if (active) setClasseurs(Array.isArray(rows) ? rows : (rows?.results ?? [])) })
      .catch(() => { if (active) setPasAJour(true) })
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
      .then(() => {
        toast.success('Classeur supprimé.')
        setClasseurs((l) => l.filter((c) => c.id !== classeur.id))
        reload()
      })
      .catch(() => toast.error('Suppression impossible.'))
  }

  const columns = [
    { id: 'titre', header: 'Titre', accessor: (r) => r.titre },
    {
      id: 'partage', header: 'Partagé', width: 100,
      accessor: (r) => (r.partage ? 'Oui' : 'Non'),
    },
    colonneSupprimer(remove),
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Classeurs</h1>
        <div className="page-subtitle">Mini-tableurs BI avec données live et formules.</div>
      </div>

      <div className="mb-4 flex justify-end">
        <Button onClick={() => setDialogOpen(true)}><Plus /> Nouveau classeur</Button>
      </div>

      {pasAJour && (
        <p role="status" className="mb-3 text-sm text-muted-foreground">
          Liste pas à jour — le serveur n’a pas répondu.{' '}
          <Button size="sm" variant="outline" onClick={reload}>Réessayer</Button>
        </p>
      )}
      {loading ? (
        <ChargementPage />
      ) : classeurs.length === 0 ? (pasAJour ? null : (
        <EmptyState
          icon={Sheet}
          title="Aucun classeur"
          description="Créez un classeur pour construire un mini-tableau de bord avec formules."
          className="my-6"
        />
      )) : (
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
