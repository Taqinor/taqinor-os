/**
 * GED26 — Corbeille documentaire (soft-delete réversible).
 *
 * Liste les documents mis en corbeille (récupérables), avec restauration
 * (annule le soft-delete) et purge définitive (effacement RÉEL, confirmé). Les
 * gardes légales (archivage GED23 / legal hold GED24) sont appliquées côté
 * serveur : un refus 403 est surfacé en toast propre, jamais un écran cassé.
 */
import { useEffect, useMemo, useState } from 'react'
import { RotateCcw, Trash2 } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, toast,
} from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import gedApi from '../../../api/gedApi'
import { errMessage } from './shared.js'

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function CorbeillePage() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [purge, setPurge] = useState(null) // document à purger (confirmation)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await gedApi.getCorbeille()
      setDocs(unpage(res.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger la corbeille.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
    load()
  }, [])

  const columns = useMemo(() => [
    { id: 'nom', header: 'Document', accessor: (r) => r.nom },
    { id: 'folder', header: 'Dossier', accessor: (r) => r.folder_nom || '—', width: 160 },
    { id: 'supprime_par', header: 'Supprimé par', accessor: (r) => r.supprime_par_nom || '—', width: 150 },
    {
      id: 'supprime_le', header: 'Supprimé le', width: 160, align: 'right',
      accessor: (r) => r.supprime_le,
      cell: (v) => formatDateTime(v),
    },
  ], [])

  const restaurer = async (r) => {
    try {
      await gedApi.restaurerCorbeille(r.id)
      toast.success('Document restauré.')
      load()
    } catch (err) { toast.error(errMessage(err)) }
  }

  const confirmerPurge = async () => {
    if (!purge) return
    try {
      await gedApi.purgerDocument(purge.id)
      toast.success('Document supprimé définitivement.')
      setPurge(null)
      load()
    } catch (err) { toast.error(errMessage(err)); setPurge(null) }
  }

  const actions = (r) => [
    { id: 'restaurer', label: 'Restaurer', icon: RotateCcw, onClick: () => restaurer(r) },
    { id: 'purger', label: 'Supprimer définitivement', icon: Trash2, destructive: true, onClick: () => setPurge(r) },
  ]

  return (
    <>
      <ListShell
        title="Corbeille"
        subtitle="Documents supprimés — restaurez-les ou videz-les définitivement."
        columns={columns}
        rows={docs}
        loading={loading}
        error={error}
        rowActions={actions}
        searchable
        exportName="corbeille-ged"
        emptyTitle="Corbeille vide"
        emptyDescription="Aucun document supprimé pour le moment."
      />
      {purge && (
        <Dialog open onOpenChange={(o) => !o && setPurge(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Supprimer définitivement ?</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Le document <strong>{purge.nom}</strong> sera effacé de manière
              irréversible. Cette action ne peut pas être annulée.
            </p>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPurge(null)}>Annuler</Button>
              <Button variant="destructive" onClick={confirmerPurge}>
                Supprimer définitivement
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}
