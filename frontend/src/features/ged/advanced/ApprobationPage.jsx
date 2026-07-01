import { useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2, XCircle, FileSignature, FilePlus2, Send, ClipboardCheck,
} from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, Tabs, TabsList, TabsTrigger, TabsContent, StatusPill, toast,
} from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import gedApi from '../../../api/gedApi'
import { StatutApprobation, StatutSignature, errMessage } from './shared.js'

/* ============================================================================
   UX45 — Approbation & signature électronique.
   ----------------------------------------------------------------------------
   Trois onglets : Approbations (workflow revue/décision GED18), Signatures
   (demandes e-sign GED30, stub no-op sans provider), et Modèles (fusion→PDF,
   dépôt en GED, GED27/28). Un document circule approbation→signature depuis
   l'UI : la carte d'un document approuvé propose « Demander la signature ».
   Toutes les données via gedApi (useState/useEffect, pas de react-query).
   ========================================================================== */

export default function ApprobationPage() {
  const [demandes, setDemandes] = useState([])
  const [signatures, setSignatures] = useState([])
  const [modeles, setModeles] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Boîtes de dialogue.
  const [reviewDoc, setReviewDoc] = useState(null)   // demander une revue
  const [decision, setDecision] = useState(null)     // { demande, type:'approuver'|'rejeter' }
  const [signFor, setSignFor] = useState(null)       // demander une signature (document)
  const [genModele, setGenModele] = useState(null)   // générer depuis un modèle

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [d, s, m, docs] = await Promise.all([
        gedApi.getDemandesApprobation(),
        gedApi.getDemandesSignature(),
        gedApi.getModelesDocument({ actif: 1 }),
        gedApi.getDocumentsList(),
      ])
      setDemandes(unpage(d.data))
      setSignatures(unpage(s.data))
      setModeles(unpage(m.data))
      setDocuments(unpage(docs.data))
    } catch (err) {
      setError(errMessage(err, 'Impossible de charger les approbations.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  // ── Colonnes ──────────────────────────────────────────────────────────
  const demandeColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    { id: 'demandeur', header: 'Demandeur', accessor: (r) => r.demandeur_nom || '—', width: 140 },
    { id: 'approbateur', header: 'Approbateur', accessor: (r) => r.approbateur_nom || '—', width: 140 },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut,
      cell: (v) => <StatutApprobation status={v} />,
    },
    {
      id: 'created_at', header: 'Demandée le', width: 150, align: 'right',
      accessor: (r) => r.created_at,
      cell: (v) => formatDateTime(v),
    },
  ], [])

  const signatureColumns = useMemo(() => [
    { id: 'document', header: 'Document', accessor: (r) => r.document_nom || `#${r.document}` },
    { id: 'signataire', header: 'Signataire', accessor: (r) => r.signataire_nom || '—', width: 160 },
    { id: 'email', header: 'Email', accessor: (r) => r.signataire_email || '—', width: 200 },
    {
      id: 'statut', header: 'Statut', width: 130,
      accessor: (r) => r.statut,
      cell: (v) => <StatutSignature status={v} />,
    },
    {
      id: 'date_demande', header: 'Demandée le', width: 150, align: 'right',
      accessor: (r) => r.date_demande,
      cell: (v) => formatDateTime(v),
    },
  ], [])

  const modeleColumns = useMemo(() => [
    { id: 'nom', header: 'Modèle', accessor: (r) => r.nom },
    { id: 'categorie', header: 'Catégorie', accessor: (r) => r.categorie || '—', width: 160 },
    {
      id: 'actif', header: 'État', width: 110,
      accessor: (r) => (r.actif ? 'actif' : 'inactif'),
      cell: (v) => <StatusPill status={v} tone={v === 'actif' ? 'success' : 'neutral'} label={v === 'actif' ? 'Actif' : 'Inactif'} />,
    },
  ], [])

  // ── Actions de ligne ──────────────────────────────────────────────────
  const demandeActions = (r) => (r.statut === 'en_attente' ? [
    { id: 'approuver', label: 'Approuver', icon: CheckCircle2, onClick: () => setDecision({ demande: r, type: 'approuver' }) },
    { id: 'rejeter', label: 'Rejeter', icon: XCircle, destructive: true, onClick: () => setDecision({ demande: r, type: 'rejeter' }) },
  ] : [
    // Un document approuvé peut passer à la signature (approbation→signature).
    ...(r.statut === 'approuve'
      ? [{ id: 'signer', label: 'Demander la signature', icon: FileSignature, onClick: () => setSignFor({ id: r.document, nom: r.document_nom }) }]
      : []),
  ])

  const signatureActions = (r) => (r.statut === 'en_attente' ? [
    { id: 'signe', label: 'Marquer comme signée', icon: ClipboardCheck, onClick: () => markSigned(r) },
  ] : [])

  const modeleActions = (r) => [
    { id: 'generer', label: 'Générer un document', icon: FilePlus2, onClick: () => setGenModele(r) },
  ]

  // ── Mutations ─────────────────────────────────────────────────────────
  const markSigned = async (r) => {
    try {
      await gedApi.marquerSigne(r.id)
      toast.success('Signature enregistrée.')
      load()
    } catch (err) { toast.error(errMessage(err)) }
  }

  return (
    <>
      <Tabs defaultValue="approbations">
        <TabsList className="flex-wrap">
          <TabsTrigger value="approbations">Approbations</TabsTrigger>
          <TabsTrigger value="signatures">Signatures</TabsTrigger>
          <TabsTrigger value="modeles">Modèles</TabsTrigger>
        </TabsList>

        <TabsContent value="approbations">
          <ListShell
            title="Approbations & revue"
            subtitle="Workflow de validation documentaire (revue → décision)."
            actions={<Button onClick={() => setReviewDoc({})}><Send /> Demander une revue</Button>}
            columns={demandeColumns}
            rows={demandes}
            loading={loading}
            error={error}
            rowActions={demandeActions}
            searchable
            exportName="demandes-approbation"
            emptyTitle="Aucune demande"
            emptyDescription="Lancez une demande de revue sur un document."
          />
        </TabsContent>

        <TabsContent value="signatures">
          <ListShell
            title="Signatures électroniques"
            subtitle="Demandes de signature (mode local tant qu'aucun prestataire e-sign n'est configuré)."
            actions={<Button onClick={() => setSignFor({})}><FileSignature /> Nouvelle demande</Button>}
            columns={signatureColumns}
            rows={signatures}
            loading={loading}
            error={error}
            rowActions={signatureActions}
            searchable
            exportName="demandes-signature"
            emptyTitle="Aucune demande de signature"
            emptyDescription="Créez une demande de signature sur un document."
          />
        </TabsContent>

        <TabsContent value="modeles">
          <ListShell
            title="Modèles de documents"
            subtitle="Fusion (attestations, courriers) → PDF déposé en GED."
            columns={modeleColumns}
            rows={modeles}
            loading={loading}
            error={error}
            rowActions={modeleActions}
            searchable
            exportName="modeles-document"
            emptyTitle="Aucun modèle"
            emptyDescription="Créez un modèle de document (fusion → PDF)."
          />
        </TabsContent>
      </Tabs>

      {reviewDoc && (
        <DemanderRevueDialog
          documents={documents}
          onClose={() => setReviewDoc(null)}
          onDone={() => { setReviewDoc(null); load() }}
        />
      )}
      {decision && (
        <DecisionDialog
          decision={decision}
          onClose={() => setDecision(null)}
          onDone={() => { setDecision(null); load() }}
        />
      )}
      {signFor && (
        <DemanderSignatureDialog
          documents={documents}
          preselect={signFor.id ? signFor : null}
          onClose={() => setSignFor(null)}
          onDone={() => { setSignFor(null); load() }}
        />
      )}
      {genModele && (
        <GenererModeleDialog
          modele={genModele}
          onClose={() => setGenModele(null)}
          onDone={() => { setGenModele(null); load() }}
        />
      )}
    </>
  )
}

// Déscelle une réponse paginée DRF ({results:[…]}) ou une liste brute.
function unpage(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

// ── Dialogues ─────────────────────────────────────────────────────────────

function DemanderRevueDialog({ documents, onClose, onDone }) {
  const [documentId, setDocumentId] = useState('')
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    setSaving(true)
    try {
      await gedApi.demanderRevue(documentId, { commentaire })
      toast.success('Demande de revue envoyée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Demander une revue</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId}>
              <SelectTrigger><SelectValue placeholder="Choisir un document…" /></SelectTrigger>
              <SelectContent>
                {documents.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Commentaire (optionnel)</Label>
            <Textarea value={commentaire} onChange={(e) => setCommentaire(e.target.value)} rows={3} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Envoi…' : 'Envoyer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DecisionDialog({ decision, onClose, onDone }) {
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)
  const approuver = decision.type === 'approuver'

  const submit = async () => {
    setSaving(true)
    try {
      if (approuver) await gedApi.approuverDemande(decision.demande.id, { commentaire })
      else await gedApi.rejeterDemande(decision.demande.id, { commentaire })
      toast.success(approuver ? 'Demande approuvée.' : 'Demande rejetée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{approuver ? 'Approuver la demande' : 'Rejeter la demande'}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            Document : <strong>{decision.demande.document_nom || `#${decision.demande.document}`}</strong>
          </p>
          <div>
            <Label>Commentaire (optionnel)</Label>
            <Textarea value={commentaire} onChange={(e) => setCommentaire(e.target.value)} rows={3} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button variant={approuver ? 'default' : 'destructive'} onClick={submit} disabled={saving}>
            {saving ? '…' : (approuver ? 'Approuver' : 'Rejeter')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DemanderSignatureDialog({ documents, preselect, onClose, onDone }) {
  const [documentId, setDocumentId] = useState(preselect ? String(preselect.id) : '')
  const [nom, setNom] = useState('')
  const [email, setEmail] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    if (!nom.trim() || !email.trim()) { toast.error('Nom et email du signataire requis.'); return }
    setSaving(true)
    try {
      await gedApi.createDemandeSignature({
        document: documentId, signataire_nom: nom.trim(), signataire_email: email.trim(),
      })
      toast.success('Demande de signature créée.')
      onDone()
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Demander une signature</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <div>
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId} disabled={!!preselect}>
              <SelectTrigger><SelectValue placeholder="Choisir un document…" /></SelectTrigger>
              <SelectContent>
                {(preselect ? [{ id: preselect.id, nom: preselect.nom }] : documents).map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>{d.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Nom du signataire</Label>
            <Input value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div>
            <Label>Email du signataire</Label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? 'Création…' : 'Créer la demande'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function GenererModeleDialog({ modele, onClose, onDone }) {
  const [saving, setSaving] = useState(false)

  const generer = async () => {
    setSaving(true)
    try {
      const res = await gedApi.genererModele(modele.id, {})
      toast.success(res.data?.created ? 'Document généré et classé.' : 'Document déjà généré.')
      onDone()
    } catch (err) { toast.error(errMessage(err, 'Génération indisponible (moteur PDF).')) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Générer depuis « {modele.nom} »</DialogTitle></DialogHeader>
        <p className="text-sm text-muted-foreground">
          Le modèle est fusionné et le PDF est déposé dans la GED (classement automatique).
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={generer} disabled={saving}>{saving ? 'Génération…' : 'Générer'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
