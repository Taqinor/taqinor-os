import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, Tag as TagIcon, Link2, Unlink } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, Tag, Tabs, TabsList, TabsTrigger, TabsContent, toast,
} from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import gedApi from '../../../api/gedApi'
import { errMessage, CIBLES_LIEN } from './shared.js'

/* ============================================================================
   UX47 — Tags & liens transverses.
   ----------------------------------------------------------------------------
   Onglets : Taxonomie (tags hiérarchiques GED9 + affectation à un document) et
   Liens (liens polymorphes document↔lead/client/devis/facture/chantier/ticket
   GED6, montrés des deux côtés via `target_model`/`target_label`). Données via
   gedApi (useState/useEffect).
   ========================================================================== */

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function TagsPage() {
  const [tags, setTags] = useState([])
  const [assignments, setAssignments] = useState([])
  const [liens, setLiens] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showTag, setShowTag] = useState(false)
  const [showAssign, setShowAssign] = useState(false)
  const [showLien, setShowLien] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [t, a, l, docs] = await Promise.all([
        gedApi.getTags(),
        gedApi.getTagAssignments(),
        gedApi.getLiens(),
        gedApi.getDocumentsList(),
      ])
      setTags(unpage(t.data))
      setAssignments(unpage(a.data))
      setLiens(unpage(l.data))
      setDocuments(unpage(docs.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les tags.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  // ── Tags ─────────────────────────────────────────────────────────────────
  const tagColumns = useMemo(() => [
    {
      id: 'nom', header: 'Tag', accessor: (r) => r.nom,
      cell: (v, r) => <Tag style={r.couleur ? { borderColor: r.couleur } : undefined}>{v}</Tag>,
    },
    { id: 'chemin', header: 'Chemin', accessor: (r) => r.chemin || r.nom },
    { id: 'parent', header: 'Parent', accessor: (r) => r.parent_nom || '—', width: 150 },
    {
      id: 'count', header: 'Documents', width: 120, align: 'right',
      accessor: (r) => r.document_count ?? 0,
    },
  ], [])

  const tagActions = (r) => [
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteTag(r.id); toast.success('Tag supprimé.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  const assignColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    {
      id: 'tag', header: 'Tag', accessor: (r) => r.tag_nom,
      cell: (v) => <Tag>{v}</Tag>,
    },
    {
      id: 'created_at', header: 'Affecté le', width: 150, align: 'right',
      accessor: (r) => r.created_at, cell: (v) => formatDateTime(v),
    },
  ], [])

  const assignActions = (r) => [
    {
      id: 'detacher', label: 'Détacher', icon: Unlink, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteTagAssignment(r.id); toast.success('Tag détaché.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  // ── Liens polymorphes ─────────────────────────────────────────────────────
  const lienColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    {
      id: 'cible', header: 'Objet lié',
      accessor: (r) => `${cibleLabel(r.target_model)} — ${r.target_label || `#${r.target_id}`}`,
    },
    { id: 'type', header: 'Type', accessor: (r) => cibleLabel(r.target_model), width: 160 },
    {
      id: 'created_at', header: 'Lié le', width: 150, align: 'right',
      accessor: (r) => r.created_at, cell: (v) => formatDateTime(v),
    },
  ], [])

  const lienActions = (r) => [
    {
      id: 'delier', label: 'Délier', icon: Unlink, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteLien(r.id); toast.success('Lien supprimé.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  return (
    <>
      <Tabs defaultValue="taxonomie">
        <TabsList className="flex-wrap">
          <TabsTrigger value="taxonomie">Taxonomie</TabsTrigger>
          <TabsTrigger value="affectations">Affectations</TabsTrigger>
          <TabsTrigger value="liens">Liens transverses</TabsTrigger>
        </TabsList>

        <TabsContent value="taxonomie">
          <ListShell
            title="Taxonomie de tags"
            subtitle="Tags documentaires hiérarchiques (couleur, chemin, parent)."
            actions={<Button onClick={() => setShowTag(true)}><Plus /> Nouveau tag</Button>}
            columns={tagColumns} rows={tags} loading={loading} error={error}
            rowActions={tagActions} searchable exportName="tags"
            emptyTitle="Aucun tag" emptyDescription="Créez votre premier tag."
          />
        </TabsContent>

        <TabsContent value="affectations">
          <ListShell
            title="Affectations tag ↔ document"
            subtitle="Application d'un tag de la taxonomie à un document."
            actions={<Button onClick={() => setShowAssign(true)}><TagIcon /> Affecter un tag</Button>}
            columns={assignColumns} rows={assignments} loading={loading} error={error}
            rowActions={assignActions} searchable exportName="tag-assignments"
            emptyTitle="Aucune affectation" emptyDescription="Affectez un tag à un document."
          />
        </TabsContent>

        <TabsContent value="liens">
          <ListShell
            title="Liens transverses"
            subtitle="Rattachement d'un document à un lead, client, devis, facture, chantier ou ticket SAV."
            actions={<Button onClick={() => setShowLien(true)}><Link2 /> Nouveau lien</Button>}
            columns={lienColumns} rows={liens} loading={loading} error={error}
            rowActions={lienActions} searchable exportName="liens"
            emptyTitle="Aucun lien" emptyDescription="Rattachez un document à un objet métier."
          />
        </TabsContent>
      </Tabs>

      {showTag && (
        <TagDialog tags={tags} onClose={() => setShowTag(false)} onDone={() => { setShowTag(false); load() }} />
      )}
      {showAssign && (
        <AssignDialog documents={documents} tags={tags} onClose={() => setShowAssign(false)} onDone={() => { setShowAssign(false); load() }} />
      )}
      {showLien && (
        <LienDialog documents={documents} onClose={() => setShowLien(false)} onDone={() => { setShowLien(false); load() }} />
      )}
    </>
  )
}

function cibleLabel(model) {
  return CIBLES_LIEN.find((c) => c.value === model)?.label || model || '—'
}

// ── Dialogues ─────────────────────────────────────────────────────────────

function TagDialog({ tags, onClose, onDone }) {
  const [nom, setNom] = useState('')
  const [parent, setParent] = useState('')
  const [couleur, setCouleur] = useState('#2563eb')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!nom.trim()) { toast.error('Nom requis.'); return }
    setSaving(true)
    try {
      await gedApi.createTag({
        nom: nom.trim(),
        parent: parent ? Number(parent) : null,
        couleur,
        description,
      })
      toast.success('Tag créé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouveau tag</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Nom</Label>
            <Input value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div>
            <Label>Parent (optionnel)</Label>
            <Select value={parent} onValueChange={setParent}>
              <SelectTrigger><SelectValue placeholder="Aucun (racine)" /></SelectTrigger>
              <SelectContent>
                {tags.map((t) => <SelectItem key={t.id} value={String(t.id)}>{t.chemin || t.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Couleur</Label>
            <Input type="color" value={couleur} onChange={(e) => setCouleur(e.target.value)} className="h-10 w-20" />
          </div>
          <div>
            <Label>Description (optionnel)</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
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

function AssignDialog({ documents, tags, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [tagId, setTagId] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId || !tagId) { toast.error('Document et tag requis.'); return }
    setSaving(true)
    try {
      await gedApi.createTagAssignment({ document: documentId, tag: tagId })
      toast.success('Tag affecté.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Affecter un tag</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId}>
              <SelectTrigger><SelectValue placeholder="Choisir un document…" /></SelectTrigger>
              <SelectContent>
                {documents.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Tag</Label>
            <Select value={tagId} onValueChange={setTagId}>
              <SelectTrigger><SelectValue placeholder="Choisir un tag…" /></SelectTrigger>
              <SelectContent>
                {tags.map((t) => <SelectItem key={t.id} value={String(t.id)}>{t.chemin || t.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Affectation…' : 'Affecter'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function LienDialog({ documents, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [model, setModel] = useState('')
  const [objectId, setObjectId] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId || !model || !objectId) { toast.error('Document, type et identifiant requis.'); return }
    setSaving(true)
    try {
      await gedApi.createLien({ document: documentId, model, id: Number(objectId) })
      toast.success('Lien créé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouveau lien transverse</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId}>
              <SelectTrigger><SelectValue placeholder="Choisir un document…" /></SelectTrigger>
              <SelectContent>
                {documents.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Type d'objet</Label>
            <Select value={model} onValueChange={setModel}>
              <SelectTrigger><SelectValue placeholder="Choisir un type…" /></SelectTrigger>
              <SelectContent>
                {CIBLES_LIEN.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Identifiant de l'objet</Label>
            <Input type="number" min="1" step="1" value={objectId} onChange={(e) => setObjectId(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Création…' : 'Créer le lien'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
