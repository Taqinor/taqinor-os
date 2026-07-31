import { useEffect, useMemo, useState } from 'react'
import {
  Plus, Trash2, Bell, CheckCircle2, Stamp, ClipboardList,
} from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, Checkbox, Tabs, TabsList, TabsTrigger, TabsContent,
  Badge, EmptyState, Spinner, StatusPill, toast,
} from '../../../ui'
import { formatDateTime, formatNumber } from '../../../lib/format'
import gedApi from '../../../api/gedApi'
import { errMessage } from './shared.js'

/* ============================================================================
   WIR164 — GED avancée, groupe (a) : checklist de pièces (XGED8), validation
   OCR (XGED13) et tampons société (XGED16). Ces trois blocs étaient montés
   côté backend SANS AUCUN ÉCRAN (les tampons société n'avaient même pas de
   chemin d'écriture — voir apps/ged/views.py TamponSocieteViewSet, WIR164).
   ----------------------------------------------------------------------------
   PÉRIMÈTRE (à confirmer par le fondateur) : le groupe (b) — regles-dossier,
   regles-approbation, regles-acl-metadonnee, demandes-disposition, lots-envoi,
   planifications — reste NON construit ici (moteurs de règles/destruction/
   diffusion en masse, plus complexes/à risque). Backends déjà exposés
   (`/api/django/ged/{regles-dossier,regles-approbation,regles-acl-metadonnee,
   demandes-disposition,lots-envoi,planifications}/`) mais aucun écran —
   documenté ici comme NON PRIORITAIRE en attendant l'arbitrage fondateur,
   plutôt que deviné.
   ========================================================================== */

function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

export default function ChecklistPage() {
  const [folders, setFolders] = useState([])
  const [cabinets, setCabinets] = useState([])
  const [folderId, setFolderId] = useState('')
  const [checklist, setChecklist] = useState(null)
  const [exigences, setExigences] = useState([])
  const [demandes, setDemandes] = useState([])
  const [ocrEnAttente, setOcrEnAttente] = useState([])
  const [tampons, setTampons] = useState([])
  const [stampsDisponibles, setStampsDisponibles] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [showExigence, setShowExigence] = useState(false)
  const [showDemande, setShowDemande] = useState(false)
  const [showTampon, setShowTampon] = useState(false)
  const [showApposer, setShowApposer] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [f, c, ex, de, ocr, ta, sd, docs] = await Promise.all([
        gedApi.getDossiers(),
        gedApi.getCabinets(),
        gedApi.getExigences(),
        gedApi.getDemandesDocument(),
        gedApi.getValidationsOcr({ en_attente: 1 }),
        gedApi.getTamponsSociete(),
        gedApi.getStampsDisponibles(),
        gedApi.getDocumentsList(),
      ])
      setFolders(unpage(f.data))
      setCabinets(unpage(c.data))
      setExigences(unpage(ex.data))
      setDemandes(unpage(de.data))
      setOcrEnAttente(unpage(ocr.data))
      setTampons(unpage(ta.data))
      setStampsDisponibles(sd.data ?? [])
      setDocuments(unpage(docs.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger la GED avancée.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  useEffect(() => {
    if (!folderId) { setChecklist(null); return }
    gedApi.getChecklist(folderId)
      .then((r) => setChecklist(r.data))
      .catch(() => setChecklist([]))
  }, [folderId])

  // ── Checklist (dossier sélectionné) ─────────────────────────────────────
  const folderLabel = (f) => `${f.cabinet_nom ? `${f.cabinet_nom} / ` : ''}${f.nom}`

  // ── Exigences (modèles de pièces requises) ──────────────────────────────
  const exigenceColumns = useMemo(() => [
    { id: 'libelle', header: 'Pièce', accessor: (r) => r.libelle },
    {
      id: 'scope', header: 'Portée', width: 180,
      accessor: (r) => r.folder_nom || (r.cabinet ? 'Tout le cabinet' : '—'),
    },
    {
      id: 'obligatoire', header: 'Obligatoire', width: 120,
      accessor: (r) => (r.obligatoire ? 'oui' : 'non'),
      cell: (v) => <StatusPill status={v} tone={v === 'oui' ? 'warning' : 'neutral'} label={v === 'oui' ? 'Obligatoire' : 'Facultative'} />,
    },
  ], [])
  const exigenceActions = (r) => [
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteExigence(r.id); toast.success('Exigence supprimée.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  // ── Demandes de pièces ───────────────────────────────────────────────────
  const demandeColumns = useMemo(() => [
    { id: 'libelle', header: 'Pièce demandée', accessor: (r) => r.libelle },
    { id: 'folder', header: 'Dossier', accessor: (r) => r.folder_nom, width: 160 },
    {
      id: 'destinataire', header: 'Destinataire', width: 180,
      accessor: (r) => r.utilisateur_nom || r.destinataire_nom || r.destinataire_email || '—',
    },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut,
      cell: (v) => (
        <StatusPill status={v} tone={v === 'soldee' ? 'success' : v === 'annulee' ? 'neutral' : 'warning'}
          label={v === 'soldee' ? 'Soldée' : v === 'annulee' ? 'Annulée' : 'En attente'} />
      ),
    },
    {
      id: 'relances', header: 'Relances', width: 100, align: 'right',
      accessor: (r) => r.nombre_relances,
    },
  ], [])
  const demandeActions = (r) => (r.statut === 'en_attente' ? [
    {
      id: 'relancer', label: 'Relancer', icon: Bell,
      onClick: async () => {
        try { await gedApi.relancerDemandeDocument(r.id); toast.success('Relance envoyée.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ] : [])

  // ── Validation OCR ───────────────────────────────────────────────────────
  const ocrColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom },
    {
      id: 'score', header: 'Confiance', width: 120, align: 'right',
      accessor: (r) => r.score_confiance,
      cell: (v) => `${formatNumber(Math.round((v ?? 0) * 100))} %`,
    },
    {
      id: 'le', header: 'Extrait le', width: 160, align: 'right',
      accessor: (r) => r.created_at, cell: (v) => formatDateTime(v),
    },
  ], [])
  const ocrActions = (r) => [
    {
      id: 'valider', label: 'Valider', icon: CheckCircle2,
      onClick: async () => {
        try { await gedApi.validerOcr(r.id); toast.success('Extraction validée.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  // ── Tampons société ──────────────────────────────────────────────────────
  const tamponColumns = useMemo(() => [
    { id: 'libelle', header: 'Tampon', accessor: (r) => r.libelle },
    {
      id: 'cree', header: 'Créé le', width: 160, align: 'right',
      accessor: (r) => r.created_at, cell: (v) => formatDateTime(v),
    },
  ], [])
  const tamponActions = (r) => [
    {
      id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true,
      onClick: async () => {
        try { await gedApi.deleteTamponSociete(r.id); toast.success('Tampon supprimé.'); load() }
        catch (err) { toast.error(errMessage(err)) }
      },
    },
  ]

  return (
    <>
      <Tabs defaultValue="checklist">
        <TabsList className="flex-wrap">
          <TabsTrigger value="checklist"><ClipboardList size={14} /> Checklist</TabsTrigger>
          <TabsTrigger value="exigences">Exigences</TabsTrigger>
          <TabsTrigger value="demandes">Demandes de pièces</TabsTrigger>
          <TabsTrigger value="ocr">Validation OCR</TabsTrigger>
          <TabsTrigger value="tampons"><Stamp size={14} /> Tampons</TabsTrigger>
        </TabsList>

        <TabsContent value="checklist">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <Label>Dossier</Label>
                <Select value={folderId} onValueChange={setFolderId}>
                  <SelectTrigger aria-label="Choisir un dossier" className="w-72">
                    <SelectValue placeholder="Choisir un dossier…" />
                  </SelectTrigger>
                  <SelectContent>
                    {folders.map((f) => (
                      <SelectItem key={f.id} value={String(f.id)}>{folderLabel(f)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {!folderId ? (
              <EmptyState title="Choisissez un dossier" description="La checklist combine les exigences applicables et les dépôts déjà reçus." className="py-8" />
            ) : checklist === null ? <Spinner /> : checklist.length === 0 ? (
              <EmptyState title="Aucune exigence" description="Aucune pièce requise n'est définie pour ce dossier ou son cabinet." className="py-8" />
            ) : (
              <ul className="flex flex-col gap-1.5" data-testid="ged-checklist">
                {checklist.map((item) => (
                  <li key={item.exigence.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
                    <span className="flex items-center gap-2">
                      <span className="font-medium">{item.exigence.libelle}</span>
                      {item.exigence.obligatoire && <Badge tone="warning">Obligatoire</Badge>}
                    </span>
                    <StatusPill status={item.statut} tone={item.statut === 'present' ? 'success' : 'danger'}
                      label={item.statut === 'present' ? 'Présente' : 'Manquante'} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </TabsContent>

        <TabsContent value="exigences">
          <ListShell
            title="Exigences de dossier"
            subtitle="Modèles de pièces requises — par cabinet (générique) ou par dossier précis."
            actions={<Button onClick={() => setShowExigence(true)}><Plus /> Nouvelle exigence</Button>}
            columns={exigenceColumns} rows={exigences} loading={loading} error={error}
            rowActions={exigenceActions} searchable exportName="exigences-dossier"
            emptyTitle="Aucune exigence" emptyDescription="Définissez une pièce requise."
          />
        </TabsContent>

        <TabsContent value="demandes">
          <ListShell
            title="Demandes de pièces"
            subtitle="Placeholder visible dans le dossier jusqu'au dépôt correspondant (relance manuelle possible)."
            actions={<Button onClick={() => setShowDemande(true)}><Plus /> Nouvelle demande</Button>}
            columns={demandeColumns} rows={demandes} loading={loading} error={error}
            rowActions={demandeActions} searchable exportName="demandes-document"
            emptyTitle="Aucune demande" emptyDescription="Demandez une pièce nommée à un utilisateur ou un contact externe."
          />
        </TabsContent>

        <TabsContent value="ocr">
          <ListShell
            title="Validation OCR"
            subtitle="Extractions automatiques en attente de validation (score de confiance)."
            columns={ocrColumns} rows={ocrEnAttente} loading={loading} error={error}
            rowActions={ocrActions} searchable exportName="validations-ocr"
            emptyTitle="Aucune extraction en attente" emptyDescription="Les extractions OCR à valider apparaîtront ici."
          />
        </TabsContent>

        <TabsContent value="tampons">
          <ListShell
            title="Tampons de la société"
            subtitle="En plus des 3 tampons système (Payé, Validé, Confidentiel), toujours disponibles."
            actions={(
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setShowApposer(true)}>
                  <Stamp /> Apposer un tampon
                </Button>
                <Button onClick={() => setShowTampon(true)}><Plus /> Nouveau tampon</Button>
              </div>
            )}
            columns={tamponColumns} rows={tampons} loading={loading} error={error}
            rowActions={tamponActions} searchable exportName="tampons-societe"
            emptyTitle="Aucun tampon propre" emptyDescription="Ajoutez un tampon propre à votre société."
          />
        </TabsContent>
      </Tabs>

      {showExigence && (
        <ExigenceDialog cabinets={cabinets} folders={folders}
          onClose={() => setShowExigence(false)} onDone={() => { setShowExigence(false); load() }} />
      )}
      {showDemande && (
        <DemandeDialog folders={folders} exigences={exigences}
          onClose={() => setShowDemande(false)} onDone={() => { setShowDemande(false); load() }} />
      )}
      {showTampon && (
        <TamponDialog onClose={() => setShowTampon(false)} onDone={() => { setShowTampon(false); load() }} />
      )}
      {showApposer && (
        <ApposerDialog documents={documents} stamps={stampsDisponibles}
          onClose={() => setShowApposer(false)} onDone={() => { setShowApposer(false); load() }} />
      )}
    </>
  )
}

// ── Dialogues ─────────────────────────────────────────────────────────────

function ExigenceDialog({ cabinets, folders, onClose, onDone }) {
  const [libelle, setLibelle] = useState('')
  const [description, setDescription] = useState('')
  const [obligatoire, setObligatoire] = useState(true)
  const [scope, setScope] = useState('cabinet') // 'cabinet' (générique) ou 'folder' (précis)
  const [cabinetId, setCabinetId] = useState('')
  const [folderId, setFolderId] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!libelle.trim()) { toast.error('Libellé requis.'); return }
    const target = scope === 'cabinet'
      ? { cabinet: cabinetId || undefined }
      : { folder: folderId || undefined }
    if (scope === 'cabinet' && !cabinetId) { toast.error('Choisissez un cabinet.'); return }
    if (scope === 'folder' && !folderId) { toast.error('Choisissez un dossier.'); return }
    setSaving(true)
    try {
      await gedApi.createExigence({
        libelle: libelle.trim(), description, obligatoire, ...target,
      })
      toast.success('Exigence créée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouvelle exigence de dossier</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Pièce requise</Label>
            <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Ex. Attestation CNSS" />
          </div>
          <div>
            <Label>Description (optionnelle)</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
          </div>
          <div>
            <Label>Portée</Label>
            <Select value={scope} onValueChange={setScope}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="cabinet">Tout un cabinet (générique)</SelectItem>
                <SelectItem value="folder">Un dossier précis</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {scope === 'cabinet' ? (
            <div>
              <Label>Cabinet</Label>
              <Select value={cabinetId} onValueChange={setCabinetId}>
                <SelectTrigger><SelectValue placeholder="Choisir un cabinet…" /></SelectTrigger>
                <SelectContent>
                  {cabinets.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div>
              <Label>Dossier</Label>
              <Select value={folderId} onValueChange={setFolderId}>
                <SelectTrigger><SelectValue placeholder="Choisir un dossier…" /></SelectTrigger>
                <SelectContent>
                  {folders.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={obligatoire} onCheckedChange={setObligatoire} />
            Pièce obligatoire
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DemandeDialog({ folders, exigences, onClose, onDone }) {
  const [folderId, setFolderId] = useState('')
  const [exigenceId, setExigenceId] = useState('')
  const [libelle, setLibelle] = useState('')
  const [destinataireNom, setDestinataireNom] = useState('')
  const [destinataireEmail, setDestinataireEmail] = useState('')
  const [echeance, setEcheance] = useState('')
  const [saving, setSaving] = useState(false)

  const exigencesDuDossier = useMemo(
    () => exigences.filter((e) => !e.folder || String(e.folder) === folderId),
    [exigences, folderId],
  )

  const submit = async () => {
    if (!folderId) { toast.error('Sélectionnez un dossier.'); return }
    if (!libelle.trim()) { toast.error('Libellé requis.'); return }
    setSaving(true)
    try {
      await gedApi.createDemandeDocument({
        folder: folderId, exigence: exigenceId || undefined,
        libelle: libelle.trim(), destinataire_nom: destinataireNom,
        destinataire_email: destinataireEmail, echeance: echeance || undefined,
      })
      toast.success('Demande créée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouvelle demande de pièce</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Dossier</Label>
            <Select value={folderId} onValueChange={setFolderId}>
              <SelectTrigger><SelectValue placeholder="Choisir un dossier…" /></SelectTrigger>
              <SelectContent>
                {folders.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Exigence liée (optionnelle)</Label>
            <Select value={exigenceId} onValueChange={setExigenceId}>
              <SelectTrigger><SelectValue placeholder="Aucune…" /></SelectTrigger>
              <SelectContent>
                {exigencesDuDossier.map((e) => (
                  <SelectItem key={e.id} value={String(e.id)}>{e.libelle}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Pièce demandée</Label>
            <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} />
          </div>
          <div>
            <Label>Contact externe — nom (optionnel)</Label>
            <Input value={destinataireNom} onChange={(e) => setDestinataireNom(e.target.value)} />
          </div>
          <div>
            <Label>Contact externe — e-mail (optionnel)</Label>
            <Input type="email" value={destinataireEmail} onChange={(e) => setDestinataireEmail(e.target.value)} />
          </div>
          <div>
            <Label>Échéance (optionnelle)</Label>
            <Input type="date" value={echeance} onChange={(e) => setEcheance(e.target.value)} />
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

function TamponDialog({ onClose, onDone }) {
  const [libelle, setLibelle] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!libelle.trim()) { toast.error('Libellé requis.'); return }
    setSaving(true)
    try {
      await gedApi.createTamponSociete({ libelle: libelle.trim() })
      toast.success('Tampon créé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Nouveau tampon de société</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Libellé</Label>
            <Input value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="Ex. Archivé RH" />
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

function ApposerDialog({ documents, stamps, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [stamp, setStamp] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    if (!stamp) { toast.error('Choisissez un tampon.'); return }
    setSaving(true)
    try {
      const versions = await gedApi.getVersions({ document: documentId })
      const rows = unpage(versions.data)
      const derniere = rows.reduce(
        (best, v) => (!best || v.version > best.version ? v : best), null)
      if (!derniere) { toast.error('Ce document n’a aucune version.'); return }
      await gedApi.createAnnotation({
        version: derniere.id, type_annotation: 'tampon',
        page: 0, x: 10, y: 10, contenu: stamp,
      })
      toast.success('Tampon apposé.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Apposer un tampon</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId}>
              <SelectTrigger aria-label="Choisir un document">
                <SelectValue placeholder="Choisir un document…" />
              </SelectTrigger>
              <SelectContent>
                {documents.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Tampon</Label>
            <Select value={stamp} onValueChange={setStamp}>
              <SelectTrigger aria-label="Choisir un tampon">
                <SelectValue placeholder="Choisir un tampon…" />
              </SelectTrigger>
              <SelectContent>
                {stamps.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs text-muted-foreground">
            Posé sur la dernière version, en haut à gauche de la première page —
            une couche séparée (l’original n’est jamais modifié).
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Apposition…' : 'Apposer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
