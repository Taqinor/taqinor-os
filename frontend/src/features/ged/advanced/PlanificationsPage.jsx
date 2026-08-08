import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, CheckCircle2 } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, toast,
} from '../../../ui'
import { formatDate } from '../../../lib/format'
import gedApi from '../../../api/gedApi'
import { errMessage } from './shared.js'

/* ============================================================================
   PACT137 — Planifications de document (XGED15).
   ----------------------------------------------------------------------------
   Une échéance + un assigné sur un document (« relancer le J+7 »),
   volontairement LOCALE à la GED (pas `records.Activity` générique).
   Notification à échéance gérée côté serveur (best-effort) — cet écran est
   purement la liste, la création et le marquage « faite ».
   ========================================================================== */

const StatutPlanification = statusPill({
  faite: { label: 'Faite', tone: 'success' },
  en_retard: { label: 'En retard', tone: 'danger' },
  a_venir: { label: 'À venir', tone: 'warning' },
})

function statutDe(r) {
  if (r.faite) return 'faite'
  const today = new Date().toISOString().slice(0, 10)
  return r.echeance && r.echeance < today ? 'en_retard' : 'a_venir'
}

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function PlanificationsPage() {
  const [planifications, setPlanifications] = useState([])
  const [documents, setDocuments] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [p, docs, u] = await Promise.all([
        gedApi.getPlanificationsDocument(),
        gedApi.getDocumentsList(),
        gedApi.getUsers(),
      ])
      setPlanifications(unpage(p.data))
      setDocuments(unpage(docs.data))
      setUsers(unpage(u.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les planifications.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const columns = useMemo(() => [
    { id: 'libelle', header: 'Planification', accessor: (r) => r.libelle },
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}`, width: 180 },
    {
      id: 'echeance', header: 'Échéance', width: 130, align: 'right',
      accessor: (r) => r.echeance, cell: (v) => formatDate(v),
    },
    { id: 'assigne', header: 'Assigné à', accessor: (r) => r.assigne_a_nom || '—', width: 150 },
    {
      id: 'statut', header: 'État', width: 110,
      accessor: (r) => statutDe(r), cell: (v) => <StatutPlanification status={v} />,
    },
  ], [])

  const rowActions = (r) => (r.faite ? [] : [
    {
      id: 'faite', label: 'Marquer faite', icon: CheckCircle2,
      onClick: async () => {
        try {
          await gedApi.updatePlanificationDocument(r.id, { faite: true })
          toast.success('Planification marquée faite.')
          load()
        } catch (err) { toast.error(errMessage(err)) }
      },
    },
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deletePlanificationDocument(r.id); toast.success('Planification supprimée.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ])

  return (
    <>
      <ListShell
        title="Planifications de document"
        subtitle="Échéances par document (« relancer le J+7 »), triées par échéance."
        actions={<Button onClick={() => setShowCreate(true)}><Plus /> Nouvelle planification</Button>}
        columns={columns} rows={planifications} loading={loading} error={error}
        rowActions={rowActions} searchable exportName="planifications-document"
        emptyTitle="Aucune planification" emptyDescription="Créez une échéance sur un document."
      />

      {showCreate && (
        <CreatePlanificationDialog
          documents={documents} users={users}
          onClose={() => setShowCreate(false)}
          onDone={() => { setShowCreate(false); load() }}
        />
      )}
    </>
  )
}

// ── Dialogue ──────────────────────────────────────────────────────────────

function CreatePlanificationDialog({ documents, users, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [libelle, setLibelle] = useState('')
  const [echeance, setEcheance] = useState('')
  const [assigneA, setAssigneA] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    if (!libelle.trim()) { toast.error('Libellé requis.'); return }
    if (!echeance) { toast.error('Échéance requise.'); return }
    setSaving(true)
    try {
      await gedApi.createPlanificationDocument({
        document: documentId, libelle: libelle.trim(), echeance,
        assigne_a: assigneA || undefined,
      })
      toast.success('Planification créée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouvelle planification</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId}>
              <SelectTrigger aria-label="Choisir un document"><SelectValue placeholder="Choisir un document…" /></SelectTrigger>
              <SelectContent>
                {documents.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Libellé</Label>
            <Input aria-label="Libellé de la planification" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div>
            <Label>Échéance</Label>
            <Input aria-label="Échéance" type="date" value={echeance} onChange={(e) => setEcheance(e.target.value)} />
          </div>
          <div>
            <Label>Assigné à (optionnel)</Label>
            <Select value={assigneA} onValueChange={setAssigneA}>
              <SelectTrigger aria-label="Choisir un assigné"><SelectValue placeholder="Choisir un utilisateur…" /></SelectTrigger>
              <SelectContent>
                {users.map((u) => <SelectItem key={u.id} value={String(u.id)}>{u.username || u.email}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
