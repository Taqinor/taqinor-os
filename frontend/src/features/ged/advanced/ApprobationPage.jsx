import { useEffect, useMemo, useState } from 'react'
import {
  CheckCircle2, XCircle, FileSignature, FilePlus2, Send, ClipboardCheck,
  Users, Plus, Trash2, XSquare,
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
  const [multiFor, setMultiFor] = useState(null)     // XGED2 — circuit multi-signataires
  const [roles, setRoles] = useState([])             // ZGED1 — rôles réutilisables

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [d, s, m, docs, r] = await Promise.all([
        gedApi.getDemandesApprobation(),
        gedApi.getDemandesSignature(),
        gedApi.getModelesDocument({ actif: 1 }),
        gedApi.getDocumentsList(),
        // ZGED1 — rôles réutilisables (dégrade en liste vide si indisponible).
        gedApi.getRolesSignataire().catch(() => ({ data: [] })),
      ])
      setDemandes(unpage(d.data))
      setSignatures(unpage(s.data))
      setModeles(unpage(m.data))
      setDocuments(unpage(docs.data))
      setRoles(unpage(r.data))
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
    // XGED2 — annulation émetteur d'une demande encore en attente.
    { id: 'annuler', label: 'Annuler la demande', icon: XSquare, destructive: true, onClick: () => cancelSignature(r) },
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

  const cancelSignature = async (r) => {
    try {
      await gedApi.annulerDemandeSignature(r.id)
      toast.success('Demande annulée.')
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
            actions={(
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setMultiFor({})}>
                  <Users /> Circuit multi-signataires
                </Button>
                <Button onClick={() => setSignFor({})}><FileSignature /> Nouvelle demande</Button>
              </div>
            )}
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
      {multiFor && (
        <MultiSignataireDialog
          documents={documents}
          roles={roles}
          onClose={() => setMultiFor(null)}
          onDone={() => { setMultiFor(null); load() }}
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

// ── XGED2/XGED3 — Circuit multi-signataires + champs positionnés ────────────
// Deux étapes : (1) définir le document, le routage (séquentiel/parallèle) et
// les destinataires ORDONNÉS (ordre/rôle) → creer-multi ; (2) une fois la
// demande créée, poser les champs de signature positionnés (page/x/y) via le
// CRUD champs-signature. L'étape 2 est facultative (fermer suffit).
const TYPE_CHAMP_OPTIONS = [
  { value: 'signature', label: 'Signature' },
  { value: 'initiales', label: 'Initiales' },
  { value: 'date', label: 'Date' },
  { value: 'texte', label: 'Texte' },
  { value: 'case', label: 'Case à cocher' },
]

function MultiSignataireDialog({ documents, roles, onClose, onDone }) {
  const [etape, setEtape] = useState(1)
  const [documentId, setDocumentId] = useState('')
  const [routage, setRoutage] = useState('sequentiel')
  const [destinataires, setDestinataires] = useState([
    { nom: '', email: '', role: '', role_signataire: '' },
  ])
  const [saving, setSaving] = useState(false)
  const [demande, setDemande] = useState(null)

  const majDest = (i, patch) =>
    setDestinataires((list) => list.map((d, idx) => (idx === i ? { ...d, ...patch } : d)))
  const ajouterDest = () =>
    setDestinataires((list) => [...list, { nom: '', email: '', role: '', role_signataire: '' }])
  const retirerDest = (i) =>
    setDestinataires((list) => (list.length > 1 ? list.filter((_, idx) => idx !== i) : list))

  const creer = async () => {
    if (!documentId) { toast.error('Sélectionnez un document.'); return }
    const valides = destinataires.filter((d) => d.nom.trim())
    if (!valides.length) { toast.error('Ajoutez au moins un destinataire nommé.'); return }
    setSaving(true)
    try {
      const res = await gedApi.creerDemandeMultiSignataires({
        document: documentId,
        routage,
        destinataires: valides.map((d, i) => ({
          nom: d.nom.trim(),
          email: d.email.trim() || undefined,
          role: d.role.trim() || undefined,
          role_signataire: d.role_signataire || undefined,
          ordre: i + 1,
        })),
      })
      setDemande(res.data)
      toast.success('Circuit de signature créé.')
      setEtape(2)
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {etape === 1 ? 'Nouveau circuit de signature' : 'Champs de signature (facultatif)'}
          </DialogTitle>
        </DialogHeader>

        {etape === 1 ? (
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
              <Label>Ordre de signature</Label>
              <Select value={routage} onValueChange={setRoutage}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="sequentiel">Séquentiel (un après l’autre)</SelectItem>
                  <SelectItem value="parallele">Parallèle (tous en même temps)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label>Destinataires (dans l’ordre)</Label>
              {destinataires.map((d, i) => (
                <div key={i} className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-muted-foreground" style={{ width: 20 }}>{i + 1}.</span>
                  <Input
                    placeholder="Nom" value={d.nom} style={{ flex: '1 1 120px' }}
                    onChange={(e) => majDest(i, { nom: e.target.value })}
                  />
                  <Input
                    placeholder="Email" type="email" value={d.email} style={{ flex: '1 1 140px' }}
                    onChange={(e) => majDest(i, { email: e.target.value })}
                  />
                  {roles.length > 0 ? (
                    <Select
                      value={d.role_signataire}
                      onValueChange={(v) => majDest(i, { role_signataire: v })}
                    >
                      <SelectTrigger style={{ width: 130 }}><SelectValue placeholder="Rôle" /></SelectTrigger>
                      <SelectContent>
                        {roles.map((rr) => (
                          <SelectItem key={rr.id} value={String(rr.id)}>{rr.nom}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      placeholder="Rôle" value={d.role} style={{ width: 120 }}
                      onChange={(e) => majDest(i, { role: e.target.value })}
                    />
                  )}
                  <Button
                    variant="ghost" size="icon" type="button"
                    aria-label={`Retirer le destinataire ${i + 1}`}
                    onClick={() => retirerDest(i)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
              <Button variant="outline" size="sm" type="button" onClick={ajouterDest}>
                <Plus /> Ajouter un destinataire
              </Button>
            </div>
          </div>
        ) : (
          <ChampsSignatureEditor demande={demande} />
        )}

        <DialogFooter>
          {etape === 1 ? (
            <>
              <Button variant="outline" onClick={onClose}>Annuler</Button>
              <Button onClick={creer} disabled={saving}>
                {saving ? 'Création…' : 'Créer le circuit'}
              </Button>
            </>
          ) : (
            <Button onClick={onDone}>Terminer</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// XGED3 — pose de champs de signature positionnés sur une demande créée. Chaque
// champ porte un type, une page et une position (x/y en %) ; le rendu public
// (PublicSignaturePage) demande la valeur des champs de saisie requis.
function ChampsSignatureEditor({ demande }) {
  const [champs, setChamps] = useState([])
  const [type, setType] = useState('signature')
  const [page, setPage] = useState('1')
  const [role, setRole] = useState('')
  const [requis, setRequis] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!demande?.id) return
    gedApi.getChampsSignature({ demande: demande.id })
      .then((res) => setChamps(unpage(res.data)))
      .catch(() => {})
  }, [demande?.id])

  const ajouter = async () => {
    setSaving(true)
    try {
      const res = await gedApi.createChampSignature({
        demande: demande.id, type_champ: type, page: Number(page) || 1,
        x: 10, y: 10, largeur: 30, hauteur: 8,
        role: role.trim() || undefined, requis,
      })
      setChamps((list) => [...list, res.data])
      toast.success('Champ ajouté.')
    } catch (err) { toast.error(errMessage(err)) } finally { setSaving(false) }
  }

  const supprimer = async (id) => {
    try {
      await gedApi.deleteChampSignature(id)
      setChamps((list) => list.filter((c) => c.id !== id))
    } catch (err) { toast.error(errMessage(err)) }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Ajoutez les champs à faire remplir/signer. Vous pouvez terminer sans en poser.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <Label>Type</Label>
          <Select value={type} onValueChange={setType}>
            <SelectTrigger style={{ width: 150 }}><SelectValue /></SelectTrigger>
            <SelectContent>
              {TYPE_CHAMP_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label>Page</Label>
          <Input type="number" min="1" value={page} style={{ width: 80 }}
            onChange={(e) => setPage(e.target.value)} />
        </div>
        <div>
          <Label>Rôle (optionnel)</Label>
          <Input value={role} style={{ width: 120 }}
            onChange={(e) => setRole(e.target.value)} />
        </div>
        <label className="flex items-center gap-1 text-sm" style={{ marginBottom: 6 }}>
          <input type="checkbox" checked={requis} onChange={(e) => setRequis(e.target.checked)} />
          Requis
        </label>
        <Button size="sm" type="button" onClick={ajouter} disabled={saving}>
          <Plus /> Ajouter
        </Button>
      </div>
      {champs.length > 0 && (
        <ul className="flex flex-col gap-1">
          {champs.map((c) => (
            <li key={c.id} className="flex items-center justify-between text-sm">
              <span>
                {(TYPE_CHAMP_OPTIONS.find((o) => o.value === c.type_champ)?.label) || c.type_champ}
                {' '}· page {c.page}{c.role ? ` · ${c.role}` : ''}{c.requis ? ' · requis' : ''}
              </span>
              <Button variant="ghost" size="icon" type="button"
                aria-label="Supprimer le champ" onClick={() => supprimer(c.id)}>
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
