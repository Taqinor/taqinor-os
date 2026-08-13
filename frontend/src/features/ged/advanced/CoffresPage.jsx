import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2, FileText } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, toast,
} from '../../../ui'
import gedApi from '../../../api/gedApi'
import crmApi from '../../../api/crmApi'
import { errMessage } from './shared.js'

/* ============================================================================
   PACT131 — Coffres-forts documentaires (GED8).
   ----------------------------------------------------------------------------
   Un coffre est un espace confidentiel appartenant à UN employé OU UN client
   (jamais les deux) : `selectors.coffres_for_user` filtre déjà la liste côté
   serveur (un employé ne voit que les siens, un admin voit tous ceux de sa
   société) — cet écran n'ajoute AUCUN filtrage supplémentaire côté client.
   ========================================================================== */

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function CoffresPage() {
  const [coffres, setCoffres] = useState([])
  const [clients, setClients] = useState([])
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [viewDocs, setViewDocs] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [c, cl, u] = await Promise.all([
        gedApi.getCoffres(),
        crmApi.getClients().catch(() => ({ data: [] })),
        gedApi.getUsers().catch(() => ({ data: [] })),
      ])
      setCoffres(unpage(c.data))
      setClients(unpage(cl.data))
      setUsers(unpage(u.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les coffres.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const clientNom = (id) => clients.find((c) => String(c.id) === String(id))?.nom

  const columns = useMemo(() => [
    { id: 'nom', header: 'Coffre', accessor: (r) => r.nom },
    { id: 'description', header: 'Description', accessor: (r) => r.description || '—' },
    {
      id: 'proprietaire', header: 'Propriétaire', width: 200,
      accessor: (r) => (r.proprietaire
        ? `Employé — ${r.proprietaire_nom || `#${r.proprietaire}`}`
        : `Client — ${clientNom(r.client) || `#${r.client}`}`),
    },
    {
      id: 'documents', header: 'Documents', width: 110, align: 'right',
      accessor: (r) => r.document_count ?? 0,
    },
  ], [clients])

  const rowActions = (r) => [
    { id: 'documents', label: 'Voir les documents', icon: FileText, onClick: () => setViewDocs(r) },
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteCoffre(r.id); toast.success('Coffre supprimé.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  return (
    <>
      <ListShell
        title="Coffres-forts documentaires"
        subtitle="Espaces confidentiels par employé ou par client (ACL propriétaire + administrateur)."
        actions={<Button onClick={() => setShowCreate(true)}><Plus /> Nouveau coffre</Button>}
        columns={columns} rows={coffres} loading={loading} error={error}
        rowActions={rowActions} searchable exportName="coffres"
        emptyTitle="Aucun coffre accessible" emptyDescription="Créez un coffre pour un employé ou un client."
      />

      {showCreate && (
        <CreateCoffreDialog
          clients={clients} users={users}
          onClose={() => setShowCreate(false)}
          onDone={() => { setShowCreate(false); load() }}
        />
      )}
      {viewDocs && (
        <CoffreDocumentsDialog coffre={viewDocs} onClose={() => setViewDocs(null)} />
      )}
    </>
  )
}

// ── Dialogues ─────────────────────────────────────────────────────────────

function CreateCoffreDialog({ clients, users, onClose, onDone }) {
  const [nom, setNom] = useState('')
  const [description, setDescription] = useState('')
  const [type, setType] = useState('employe')
  const [proprietaireId, setProprietaireId] = useState('')
  const [clientId, setClientId] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!nom.trim()) { toast.error('Nom requis.'); return }
    if (type === 'employe' && !proprietaireId) { toast.error('Choisissez un employé.'); return }
    if (type === 'client' && !clientId) { toast.error('Choisissez un client.'); return }
    setSaving(true)
    try {
      await gedApi.createCoffre({
        nom: nom.trim(),
        description: description.trim(),
        proprietaire: type === 'employe' ? proprietaireId : undefined,
        client: type === 'client' ? clientId : undefined,
      })
      toast.success('Coffre créé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouveau coffre</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Nom</Label>
            <Input aria-label="Nom du coffre" value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div>
            <Label>Description (optionnelle)</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          <div>
            <Label>Propriétaire</Label>
            <Select value={type} onValueChange={(v) => { setType(v); setProprietaireId(''); setClientId('') }}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="employe">Employé</SelectItem>
                <SelectItem value="client">Client</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {type === 'employe' ? (
            <div>
              <Label>Employé</Label>
              <Select value={proprietaireId} onValueChange={setProprietaireId}>
                <SelectTrigger aria-label="Choisir un employé"><SelectValue placeholder="Choisir un employé…" /></SelectTrigger>
                <SelectContent>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={String(u.id)}>{u.username || u.email || `#${u.id}`}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div>
              <Label>Client</Label>
              <Select value={clientId} onValueChange={setClientId}>
                <SelectTrigger aria-label="Choisir un client"><SelectValue placeholder="Choisir un client…" /></SelectTrigger>
                <SelectContent>
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function CoffreDocumentsDialog({ coffre, onClose }) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    gedApi.getCoffreDocuments(coffre.id)
      .then((res) => setDocuments(unpage(res.data)))
      .catch((err) => setError(errMessage(err, 'Impossible de charger les documents.')))
      .finally(() => setLoading(false))
  }, [coffre.id])

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Documents — {coffre.nom}</DialogTitle></DialogHeader>
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && !error && documents.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucun document classé dans ce coffre.</p>
        )}
        {!loading && documents.length > 0 && (
          <ul className="flex flex-col gap-1">
            {documents.map((d) => <li key={d.id} className="text-sm">{d.nom}</li>)}
          </ul>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
