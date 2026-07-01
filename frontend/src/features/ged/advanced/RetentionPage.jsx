import { useEffect, useMemo, useState } from 'react'
import {
  Plus, Trash2, Archive, Lock, Unlock, Link2, XCircle, ShieldAlert,
} from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, Checkbox, Tabs, TabsList, TabsTrigger, TabsContent,
  Card, Stat, StatusPill, toast,
} from '../../../ui'
import { formatDateTime, formatNumber } from '../../../lib/format'
import gedApi from '../../../api/gedApi'
import { ActionEcheance, errMessage, formatOctets } from './shared.js'

/* ============================================================================
   UX46 — Rétention, archivage légal & partage.
   ----------------------------------------------------------------------------
   Onglets : Politiques (durées de conservation GED22), Échus (documents
   dépassés — consultatif), Archivages légaux (write-once GED23), Legal holds
   (gel anti-suppression GED24 — la levée peut renvoyer 403, surfacé en toast),
   Partages (liens publics tokenisés GED20 : expiry/quota/révocation), et
   Stockage (quota GED36 + journal d'accès GED35).
   ========================================================================== */

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function RetentionPage() {
  const [politiques, setPolitiques] = useState([])
  const [echus, setEchus] = useState([])
  const [archivages, setArchivages] = useState([])
  const [holds, setHolds] = useState([])
  const [partages, setPartages] = useState([])
  const [journal, setJournal] = useState([])
  const [documents, setDocuments] = useState([])
  const [quota, setQuota] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showPolitique, setShowPolitique] = useState(false)
  const [showPartage, setShowPartage] = useState(false)
  const [showHold, setShowHold] = useState(false)
  const [showArchivage, setShowArchivage] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [p, e, a, h, pa, j, docs, q] = await Promise.all([
        gedApi.getPolitiquesRetention(),
        gedApi.getDocumentsEchus(),
        gedApi.getArchivagesLegaux(),
        gedApi.getLegalHolds(),
        gedApi.getPartages(),
        gedApi.getJournalAcces(),
        gedApi.getDocumentsList(),
        gedApi.getQuotaEtat(),
      ])
      setPolitiques(unpage(p.data))
      setEchus(unpage(e.data))
      setArchivages(unpage(a.data))
      setHolds(unpage(h.data))
      setPartages(unpage(pa.data))
      setJournal(unpage(j.data))
      setDocuments(unpage(docs.data))
      setQuota(q.data)
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger la rétention.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  // ── Politiques ──────────────────────────────────────────────────────────
  const politiqueColumns = useMemo(() => [
    { id: 'nom', header: 'Politique', accessor: (r) => r.nom },
    { id: 'scope', header: 'Portée', accessor: (r) => r.cabinet_nom || r.folder_nom || r.type_document || 'Société', width: 160 },
    {
      id: 'duree', header: 'Conservation', width: 140, align: 'right',
      accessor: (r) => r.duree_conservation_jours,
      cell: (v) => `${formatNumber(v)} j`,
    },
    {
      id: 'action', header: 'À échéance', width: 130,
      accessor: (r) => r.action_echeance,
      cell: (v) => <ActionEcheance status={v} />,
    },
    {
      id: 'actif', header: 'État', width: 100,
      accessor: (r) => (r.actif ? 'actif' : 'inactif'),
      cell: (v) => <StatusPill status={v} tone={v === 'actif' ? 'success' : 'neutral'} label={v === 'actif' ? 'Actif' : 'Inactif'} />,
    },
  ], [])

  const politiqueActions = (r) => [
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deletePolitiqueRetention(r.id); toast.success('Politique supprimée.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  const echusColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom },
    { id: 'politique', header: 'Politique', accessor: (r) => r.politique_nom, width: 180 },
    {
      id: 'depasses', header: 'Jours dépassés', width: 150, align: 'right',
      accessor: (r) => r.jours_depasses,
      cell: (v) => <span className="font-medium text-destructive">{formatNumber(v)} j</span>,
    },
    {
      id: 'action', header: 'Action prévue', width: 130,
      accessor: (r) => r.action_echeance,
      cell: (v) => <ActionEcheance status={v} />,
    },
  ], [])

  const archivageColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    { id: 'motif', header: 'Motif', accessor: (r) => r.motif || '—' },
    { id: 'par', header: 'Par', accessor: (r) => r.archive_par_nom || '—', width: 140 },
    {
      id: 'retain', header: 'Conservé jusqu\'au', width: 160,
      accessor: (r) => r.object_lock_retain_until || '—',
    },
    {
      id: 'le', header: 'Archivé le', width: 150, align: 'right',
      accessor: (r) => r.archive_le, cell: (v) => formatDateTime(v),
    },
  ], [])

  const holdColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    { id: 'motif', header: 'Motif', accessor: (r) => r.motif || '—' },
    {
      id: 'actif', header: 'État', width: 110,
      accessor: (r) => (r.actif ? 'actif' : 'leve'),
      cell: (v) => <StatusPill status={v} tone={v === 'actif' ? 'danger' : 'neutral'} label={v === 'actif' ? 'Actif' : 'Levé'} />,
    },
    { id: 'par', header: 'Posé par', accessor: (r) => r.place_par_nom || '—', width: 140 },
    {
      id: 'pose', header: 'Posé le', width: 150, align: 'right',
      accessor: (r) => r.date_pose, cell: (v) => formatDateTime(v),
    },
  ], [])

  const holdActions = (r) => (r.actif ? [
    {
      id: 'lever', label: 'Lever le hold', icon: Unlock,
      onClick: async () => {
        try {
          const res = await gedApi.leverLegalHold(r.id)
          toast.success(`${res.data?.leves ?? 0} rétention(s) levée(s).`)
          load()
        } catch (err) {
          // GED24 — la levée peut être refusée (403) : surfacer proprement.
          toast.error(errMessage(err, 'Levée refusée pour ce document.'))
        }
      },
    },
  ] : [])

  const partageColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    {
      id: 'lien', header: 'Lien public', accessor: (r) => r.public_url,
      cell: (v) => <span className="truncate font-mono text-xs" title={v}>{v}</span>,
    },
    {
      id: 'expire', header: 'Expire', width: 150,
      accessor: (r) => r.expires_at, cell: (v) => (v ? formatDateTime(v) : 'Jamais'),
    },
    {
      id: 'quota', header: 'Téléch.', width: 120, align: 'right',
      accessor: (r) => r.telechargements,
      cell: (v, r) => `${formatNumber(v)}${r.quota_max ? ` / ${formatNumber(r.quota_max)}` : ''}`,
    },
    {
      id: 'etat', header: 'État', width: 120,
      accessor: (r) => (r.actif && r.is_accessible ? 'actif' : 'inactif'),
      cell: (v) => <StatusPill status={v} tone={v === 'actif' ? 'success' : 'neutral'} label={v === 'actif' ? 'Actif' : 'Inactif'} />,
    },
  ], [])

  const partageActions = (r) => (r.actif ? [
    {
      id: 'revoquer', label: 'Révoquer', icon: XCircle, destructive: true,
      onClick: async () => {
        try { await gedApi.revoquerPartage(r.id); toast.success('Partage révoqué.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ] : [])

  const journalColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    { id: 'utilisateur', header: 'Utilisateur', accessor: (r) => r.utilisateur_nom || 'Public', width: 150 },
    { id: 'type', header: 'Type d\'accès', accessor: (r) => r.type_acces, width: 140 },
    { id: 'ip', header: 'IP', accessor: (r) => r.adresse_ip || '—', width: 130 },
    {
      id: 'le', header: 'Le', width: 150, align: 'right',
      accessor: (r) => r.created_at, cell: (v) => formatDateTime(v),
    },
  ], [])

  return (
    <>
      <Tabs defaultValue="politiques">
        <TabsList className="flex-wrap">
          <TabsTrigger value="politiques">Politiques</TabsTrigger>
          <TabsTrigger value="echus">Échus</TabsTrigger>
          <TabsTrigger value="archivages">Archivages légaux</TabsTrigger>
          <TabsTrigger value="holds">Legal holds</TabsTrigger>
          <TabsTrigger value="partages">Partages</TabsTrigger>
          <TabsTrigger value="stockage">Stockage</TabsTrigger>
        </TabsList>

        <TabsContent value="politiques">
          <ListShell
            title="Politiques de rétention"
            subtitle="Durée de conservation par classe de documents (consultatif — aucune suppression automatique)."
            actions={<Button onClick={() => setShowPolitique(true)}><Plus /> Nouvelle politique</Button>}
            columns={politiqueColumns} rows={politiques} loading={loading} error={error}
            rowActions={politiqueActions} searchable exportName="politiques-retention"
            emptyTitle="Aucune politique" emptyDescription="Définissez une durée de conservation."
          />
        </TabsContent>

        <TabsContent value="echus">
          <ListShell
            title="Documents échus"
            subtitle="Documents ayant dépassé leur durée de conservation (purement consultatif)."
            columns={echusColumns} rows={echus} loading={loading} error={error}
            searchable exportName="documents-echus"
            emptyTitle="Aucun document échu" emptyDescription="Aucun document n'a dépassé sa politique."
          />
        </TabsContent>

        <TabsContent value="archivages">
          <ListShell
            title="Archivages légaux"
            subtitle="Documents figés à valeur probante (write-once, immuables)."
            actions={<Button onClick={() => setShowArchivage(true)}><Archive /> Archiver un document</Button>}
            columns={archivageColumns} rows={archivages} loading={loading} error={error}
            searchable exportName="archivages-legaux"
            emptyTitle="Aucun archivage" emptyDescription="Archivez un document à valeur probante."
          />
        </TabsContent>

        <TabsContent value="holds">
          <ListShell
            title="Rétentions légales (legal holds)"
            subtitle="Gel anti-suppression : un document sous hold ne peut être supprimé."
            actions={<Button onClick={() => setShowHold(true)}><Lock /> Poser un hold</Button>}
            columns={holdColumns} rows={holds} loading={loading} error={error}
            rowActions={holdActions} searchable exportName="legal-holds"
            emptyTitle="Aucune rétention" emptyDescription="Placez un legal hold sur un document."
          />
        </TabsContent>

        <TabsContent value="partages">
          <ListShell
            title="Partages publics"
            subtitle="Liens tokenisés (expiration, quota de téléchargements, révocation)."
            actions={<Button onClick={() => setShowPartage(true)}><Link2 /> Nouveau partage</Button>}
            columns={partageColumns} rows={partages} loading={loading} error={error}
            rowActions={partageActions} searchable exportName="partages"
            emptyTitle="Aucun partage" emptyDescription="Créez un lien de partage public."
          />
        </TabsContent>

        <TabsContent value="stockage">
          <div className="flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Card className="p-4 sm:p-5">
                <Stat label="Utilisé" value={quota ? formatOctets(quota.usage_octets) : '—'} icon={Archive} />
              </Card>
              <Card className="p-4 sm:p-5">
                <Stat label="Quota" value={quota ? (quota.illimite ? 'Illimité' : formatOctets(quota.quota_octets)) : '—'} />
              </Card>
              <Card className="p-4 sm:p-5">
                <Stat label="Restant" value={quota ? (quota.illimite ? 'Illimité' : formatOctets(quota.restant_octets)) : '—'} />
              </Card>
              <Card className="p-4 sm:p-5">
                <Stat
                  label="État"
                  value={quota?.depasse ? 'Dépassé' : 'OK'}
                  icon={quota?.depasse ? ShieldAlert : undefined}
                />
              </Card>
            </div>
            <ListShell
              title="Journal d'accès"
              subtitle="Audit des consultations / téléchargements (append-only)."
              columns={journalColumns} rows={journal} loading={loading} error={error}
              searchable exportName="journal-acces"
              emptyTitle="Aucun accès journalisé" emptyDescription="Les accès aux documents apparaîtront ici."
            />
          </div>
        </TabsContent>
      </Tabs>

      {showPolitique && (
        <PolitiqueDialog onClose={() => setShowPolitique(false)} onDone={() => { setShowPolitique(false); load() }} />
      )}
      {showArchivage && (
        <ArchivageDialog documents={documents} onClose={() => setShowArchivage(false)} onDone={() => { setShowArchivage(false); load() }} />
      )}
      {showHold && (
        <HoldDialog documents={documents} onClose={() => setShowHold(false)} onDone={() => { setShowHold(false); load() }} />
      )}
      {showPartage && (
        <PartageDialog documents={documents} onClose={() => setShowPartage(false)} onDone={() => { setShowPartage(false); load() }} />
      )}
    </>
  )
}

// ── Dialogues ─────────────────────────────────────────────────────────────

function PolitiqueDialog({ onClose, onDone }) {
  const [nom, setNom] = useState('')
  const [duree, setDuree] = useState('365')
  const [action, setAction] = useState('signaler')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!nom.trim()) { toast.error('Nom requis.'); return }
    const jours = Number(duree)
    if (!Number.isFinite(jours) || jours <= 0) { toast.error('Durée strictement positive requise.'); return }
    setSaving(true)
    try {
      await gedApi.createPolitiqueRetention({
        nom: nom.trim(), duree_conservation_jours: jours, action_echeance: action,
      })
      toast.success('Politique créée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouvelle politique de rétention</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Nom</Label>
            <Input value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div>
            <Label>Durée de conservation (jours)</Label>
            <Input type="number" min="1" step="1" value={duree} onChange={(e) => setDuree(e.target.value)} />
          </div>
          <div>
            <Label>Action à l'échéance</Label>
            <Select value={action} onValueChange={setAction}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="signaler">Signaler</SelectItem>
                <SelectItem value="archiver">Archiver</SelectItem>
                <SelectItem value="supprimer">Supprimer</SelectItem>
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

function ArchivageDialog({ documents, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [motif, setMotif] = useState('')
  const [retain, setRetain] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    setSaving(true)
    try {
      await gedApi.createArchivageLegal({
        document: documentId, motif, retain_until: retain || undefined,
      })
      toast.success('Document archivé légalement.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Archiver légalement</DialogTitle></DialogHeader>
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
            <Label>Motif (optionnel)</Label>
            <Textarea value={motif} onChange={(e) => setMotif(e.target.value)} rows={2} />
          </div>
          <div>
            <Label>Conserver jusqu'au (optionnel)</Label>
            <Input type="date" value={retain} onChange={(e) => setRetain(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Archivage…' : 'Archiver'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function HoldDialog({ documents, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [motif, setMotif] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    setSaving(true)
    try {
      await gedApi.createLegalHold({ document: documentId, motif })
      toast.success('Legal hold posé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Poser un legal hold</DialogTitle></DialogHeader>
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
            <Label>Motif (optionnel)</Label>
            <Textarea value={motif} onChange={(e) => setMotif(e.target.value)} rows={2} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Pose…' : 'Poser le hold'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PartageDialog({ documents, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [expires, setExpires] = useState('')
  const [quota, setQuota] = useState('')
  const [password, setPassword] = useState('')
  const [watermark, setWatermark] = useState(false)
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    setSaving(true)
    try {
      await gedApi.createPartage({
        document: documentId,
        expires_at: expires || undefined,
        quota_max: quota ? Number(quota) : undefined,
        password: password || undefined,
        watermark,
      })
      toast.success('Lien de partage créé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouveau partage public</DialogTitle></DialogHeader>
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
            <Label>Expire le (optionnel)</Label>
            <Input type="datetime-local" value={expires} onChange={(e) => setExpires(e.target.value)} />
          </div>
          <div>
            <Label>Quota de téléchargements (optionnel)</Label>
            <Input type="number" min="1" step="1" value={quota} onChange={(e) => setQuota(e.target.value)} />
          </div>
          <div>
            <Label>Mot de passe (optionnel)</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={watermark} onCheckedChange={setWatermark} />
            Filigraner le document servi
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Création…' : 'Créer le lien'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
