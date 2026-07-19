// GED5 — Navigateur arborescent (frontend). Vue en arbre des dossiers (GED) avec
// dépliage/repliage, et liste des documents du dossier sélectionné. Consomme les
// endpoints d'`apps/ged` (cabinets / dossiers / documents) — aucun modèle backend
// ajouté. Tout le texte est en français.
//
// U14 — La GED n'est plus en lecture seule : on ajoute les affordances d'écriture
// indispensables pour rendre le menu utilisable sur un déploiement vierge — créer
// une armoire (cabinet), créer / renommer / déplacer un dossier, et téléverser un
// document — plus un état vide qui GUIDE le premier usage. Les écritures restent
// scopées société côté serveur (jamais lues du corps de requête) ; les
// permissions (responsable/admin) sont appliquées côté backend — un refus 403 se
// traduit par un toast d'erreur, comme partout dans l'ERP.
import { useEffect, useMemo, useState } from 'react'
import {
  Folder, FolderOpen, ChevronRight, ChevronDown, FileText, Loader2, Inbox,
  RefreshCw, Plus, FolderPlus, Pencil, Upload, MoveRight, Eye, Lock, LockOpen,
  Trash2, Info, Link2,
} from 'lucide-react'
import gedApi from '../../api/gedApi'
import { formatDate } from '../../lib/format'
import {
  Card, CardContent, Button, EmptyState, Skeleton, Badge,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, DialogClose, Input, Textarea, FileUpload, toast,
} from '../../ui'
import { buildFolderTree, flattenVisible, countFolders } from './tree.js'
import GedSearch from './GedSearch.jsx'
import GedDocumentInsights from './GedDocumentInsights.jsx'
import { DataTable } from '../../ui/datatable'
import ExternalLink from '../../ui/ExternalLink'

// VX152 — colonnes structurelles seules : le rendu réel de l'en-tête et des
// lignes passe par renderHeaderRow/renderRow (échappatoire ARC49 du moteur), ce
// qui permet à la liste des documents de rejoindre DataTable sans perdre son DOM
// (cases nommées « Sélectionner … », actions par ligne, badges de verrou). Ces
// colonnes ne servent qu'à la largeur/au colSpan interne du moteur.
const GED_DOC_COLUMNS = [
  { id: 'select', header: '', sortable: false, hideable: false, reorderable: false },
  { id: 'nom', header: 'Document', sortable: false, hideable: false, reorderable: false },
  { id: 'versions', header: 'Versions', sortable: false, hideable: false, reorderable: false },
  { id: 'created_by', header: 'Créé par', sortable: false, hideable: false, reorderable: false },
  { id: 'updated', header: 'Mis à jour', sortable: false, hideable: false, reorderable: false },
  { id: 'actions', header: '', sortable: false, hideable: false, reorderable: false },
]

// Le backend pagine certains endpoints (DRF) : on accepte `results` OU le
// tableau brut, comme partout dans le frontend.
const rows = (r) => r?.data?.results ?? r?.data ?? []

// Message d'erreur lisible à partir d'une réponse axios (premier champ d'erreur
// DRF, ou message générique). Évite d'afficher un objet brut dans un toast.
const errText = (e, fallback) => {
  const d = e?.response?.data
  if (typeof d === 'string') return d
  if (d && typeof d === 'object') {
    const first = d.detail ?? Object.values(d)[0]
    if (Array.isArray(first)) return String(first[0])
    if (first) return String(first)
  }
  return fallback
}

export default function GedNavigator() {
  const [cabinets, setCabinets] = useState([])
  const [cabinetId, setCabinetId] = useState(null)
  const [folders, setFolders] = useState([])
  const [expanded, setExpanded] = useState(() => new Set())
  const [selected, setSelected] = useState(null) // dossier sélectionné | null

  const [documents, setDocuments] = useState([])
  const [loadingTree, setLoadingTree] = useState(true)
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [error, setError] = useState(null)

  // ── État des dialogues d'écriture (U14) ──
  const [cabinetDlg, setCabinetDlg] = useState(false)
  const [folderDlg, setFolderDlg] = useState(null) // { mode:'create'|'rename'|'move', folder? }
  const [uploadDlg, setUploadDlg] = useState(false)
  // GED14 — document à prévisualiser (clic sur une ligne → modale d'aperçu).
  const [previewDoc, setPreviewDoc] = useState(null)
  // WIR70 — panneau « Détails » (timeline + ACL) d'un document.
  const [insightsDoc, setInsightsDoc] = useState(null)

  // WIR70 — crée un lien de dépôt public pour le dossier sélectionné et copie
  // l'URL publique (la page PublicDepotPage fonctionne déjà côté public).
  const createDepotLink = async () => {
    if (!selected) return
    try {
      const r = await gedApi.createDepotPublic({ folder: selected.id })
      const token = r.data?.token
      const url = token ? `${window.location.origin}/ged/depot/${token}` : null
      if (url && navigator.clipboard) {
        try { await navigator.clipboard.writeText(url) } catch { /* best-effort */ }
      }
      toast.success(url ? `Lien de dépôt créé et copié : ${url}` : 'Lien de dépôt créé.')
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création du lien impossible.')
    }
  }
  // XGED14 — multi-sélection de documents pour les opérations en lot.
  const [selectedIds, setSelectedIds] = useState(() => new Set())
  const [bulkBusy, setBulkBusy] = useState(false)

  // ── Chargement des cabinets (armoires racines) ──
  const loadCabinets = (preferId) => {
    setLoadingTree(true)
    return gedApi.getCabinets()
      .then((r) => {
        const list = rows(r)
        setCabinets(list)
        if (list.length) {
          setCabinetId((c) => preferId ?? c ?? list[0].id)
        } else {
          setCabinetId(null)
          setFolders([])
          setLoadingTree(false)
        }
        setError(null)
        return list
      })
      .catch(() => { setError('Impossible de charger la GED. Réessayez.'); setLoadingTree(false) })
  }
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    loadCabinets()
  }, [])

  // ── Chargement des dossiers du cabinet courant ──
  const loadFolders = (cid) => {
    if (!cid) return
    setLoadingTree(true)
    gedApi.getDossiers({ cabinet: cid })
      .then((r) => { setFolders(rows(r)); setError(null) })
      .catch(() => setError('Impossible de charger les dossiers. Réessayez.'))
      .finally(() => setLoadingTree(false))
  }
  useEffect(() => {
    if (cabinetId == null) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    loadFolders(cabinetId)
  }, [cabinetId])

  // Bascule de cabinet : réinitialise sélection/documents/dépliage côté
  // événement (pas en effet), puis change l'id courant → l'effet recharge.
  const selectCabinet = (cid) => {
    setSelected(null)
    setDocuments([])
    setExpanded(new Set())
    setCabinetId(cid)
  }

  // ── Chargement des documents du dossier sélectionné ──
  const reloadDocuments = () => {
    if (!selected) return
    setLoadingDocs(true)
    gedApi.getDocuments({ folder: selected.id })
      .then((r) => setDocuments(rows(r)))
      .catch(() => setDocuments([]))
      .finally(() => setLoadingDocs(false))
  }
  useEffect(() => {
    if (!selected) return
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-select loading state
    setLoadingDocs(true)
    gedApi.getDocuments({ folder: selected.id })
      .then((r) => { if (alive) setDocuments(rows(r)) })
      .catch(() => { if (alive) setDocuments([]) })
      .finally(() => { if (alive) setLoadingDocs(false) })
    return () => { alive = false }
  }, [selected])

  const toggle = (id) => setExpanded((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  const selectFolder = (node) => {
    if (selected?.id !== node.id) { setDocuments([]); setSelectedIds(new Set()) }
    setSelected(node)
    if (node.hasChildren) toggle(node.id)
  }

  // XGED14 — bascule la sélection d'un document / tout sélectionner.
  const toggleSelect = (id) => setSelectedIds((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
  const toggleSelectAll = () => setSelectedIds((prev) => (
    prev.size === documents.length && documents.length > 0
      ? new Set()
      : new Set(documents.map((d) => d.id))
  ))

  // XGED14 — mise en corbeille par lot de la sélection.
  const bulkCorbeille = async () => {
    if (selectedIds.size === 0) return
    setBulkBusy(true)
    try {
      const res = await gedApi.operationsLot({
        documents: [...selectedIds], operation: 'corbeille',
      })
      const erreurs = res?.data?.erreurs || []
      if (erreurs.length) {
        toast.error(`${erreurs.length} document(s) non traité(s) (protégés).`)
      } else {
        toast.success(`${selectedIds.size} document(s) mis en corbeille.`)
      }
      setSelectedIds(new Set())
      reloadDocuments()
    } catch (err) {
      toast.error(errText(err, 'Opération en lot impossible.'))
    } finally { setBulkBusy(false) }
  }

  const tree = useMemo(() => buildFolderTree(folders), [folders])
  const visible = useMemo(() => flattenVisible(tree, expanded), [tree, expanded])
  const total = useMemo(() => countFolders(tree), [tree])

  // ── Handlers d'écriture (U14) — après succès on recharge depuis le serveur. ──
  const onCabinetCreated = (cab) => loadCabinets(cab.id)
  const onFolderChanged = () => loadFolders(cabinetId)
  const onDocumentUploaded = () => reloadDocuments()

  // ── GED16 — check-out / check-in ; GED26 — mise en corbeille ──
  const checkOut = async (d) => {
    try {
      await gedApi.checkOutDocument(d.id)
      toast.success('Document extrait (verrouillé).')
      reloadDocuments()
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.error(errText(err, 'Document déjà extrait par un autre utilisateur.'))
      } else { toast.error(errText(err, 'Extraction impossible.')) }
    }
  }
  const checkIn = async (d) => {
    try {
      await gedApi.checkInDocument(d.id)
      toast.success('Document archivé (verrou levé).')
      reloadDocuments()
    } catch (err) { toast.error(errText(err, 'Archivage impossible.')) }
  }
  const mettreEnCorbeille = async (d) => {
    try {
      await gedApi.mettreEnCorbeille(d.id)
      toast.success('Document mis en corbeille.')
      reloadDocuments()
    } catch (err) { toast.error(errText(err, 'Mise en corbeille impossible.')) }
  }

  const hasCabinet = cabinetId != null

  return (
    <div className="page">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="mr-auto">
          <h1 className="text-xl font-semibold">Documents (GED)</h1>
          <p className="text-[12.5px] text-muted-foreground">
            Arborescence documentaire — créez une armoire et un dossier, puis téléversez vos documents.
          </p>
        </div>
        {cabinets.length > 1 && (
          <div className="w-[220px]">
            <Select value={cabinetId != null ? String(cabinetId) : ''}
              onValueChange={(v) => selectCabinet(Number(v))}>
              <SelectTrigger aria-label="Choisir le cabinet"><SelectValue placeholder="Cabinet" /></SelectTrigger>
              <SelectContent>
                {cabinets.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <Button variant="secondary" onClick={() => setCabinetDlg(true)}>
          <Plus className="size-4" aria-hidden="true" /> Nouvelle armoire
        </Button>
        <Button variant="secondary" onClick={() => loadFolders(cabinetId)} disabled={!hasCabinet}>
          <RefreshCw className="size-4" aria-hidden="true" /> Actualiser
        </Button>
      </div>

      {/* GED13 — Filtres & recherche avancée (plein-texte/sémantique + tags). */}
      <div className="mb-4">
        <GedSearch />
      </div>

      {error ? (
        <EmptyState title="Erreur" description={error}
          action={<Button onClick={() => loadFolders(cabinetId)}>Réessayer</Button>} />
      ) : loadingTree ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : cabinets.length === 0 ? (
        // U14 — état vide qui GUIDE le premier usage : bouton pour créer la
        // première armoire (sans quoi l'écran paraissait cassé sur un déploiement neuf).
        <EmptyState icon={Folder}
          title="Aucune armoire documentaire"
          description="Commencez par créer une armoire (cabinet), puis ajoutez-y des dossiers et téléversez vos documents."
          action={<Button onClick={() => setCabinetDlg(true)}>
            <Plus className="size-4" aria-hidden="true" /> Créer la première armoire
          </Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-[minmax(240px,360px)_1fr]">
          {/* ── Arborescence des dossiers ── */}
          <Card>
            <CardContent className="p-2">
              <div className="mb-2 flex items-center gap-1 px-1">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {total} dossier{total > 1 ? 's' : ''}
                </span>
                <Button size="sm" variant="ghost" className="ml-auto"
                  onClick={() => setFolderDlg({ mode: 'create' })}
                  disabled={!hasCabinet}>
                  <FolderPlus className="size-4" aria-hidden="true" /> Dossier
                </Button>
              </div>
              {visible.length === 0 ? (
                // U14 — état vide de l'arbre : CTA pour créer le premier dossier.
                <div className="px-2 py-4 text-center">
                  <p className="text-sm text-muted-foreground">
                    Aucun dossier dans cette armoire.
                  </p>
                  <Button size="sm" variant="secondary" className="mt-2"
                    onClick={() => setFolderDlg({ mode: 'create' })}>
                    <FolderPlus className="size-4" aria-hidden="true" /> Créer un dossier
                  </Button>
                </div>
              ) : (
                <ul className="flex flex-col" role="tree" aria-label="Dossiers">
                  {visible.map((node) => {
                    const isOpen = expanded.has(node.id)
                    const isSel = selected?.id === node.id
                    return (
                      <li key={node.id} role="treeitem"
                        aria-expanded={node.hasChildren ? isOpen : undefined}
                        aria-selected={isSel}>
                        <button type="button"
                          className={`flex w-full items-center gap-1.5 rounded px-1.5 py-1.5 text-left text-sm hover:bg-muted${isSel ? ' bg-muted font-medium' : ''}`}
                          style={{ paddingLeft: `${node.depth * 16 + 6}px` }}
                          onClick={() => selectFolder(node)}>
                          <span className="flex size-4 shrink-0 items-center justify-center text-muted-foreground">
                            {node.hasChildren
                              ? (isOpen
                                ? <ChevronDown className="size-3.5" aria-hidden="true" />
                                : <ChevronRight className="size-3.5" aria-hidden="true" />)
                              : null}
                          </span>
                          {node.hasChildren && isOpen
                            ? <FolderOpen className="size-4 shrink-0 text-primary" aria-hidden="true" />
                            : <Folder className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
                          <span className="truncate">{node.nom}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* ── Documents du dossier sélectionné ── */}
          <Card>
            <CardContent className="p-0">
              {!selected ? (
                <EmptyState icon={Folder}
                  title="Aucun dossier sélectionné"
                  description="Sélectionnez un dossier dans l'arborescence pour afficher ses documents." />
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
                    <FolderOpen className="size-4 text-primary" aria-hidden="true" />
                    <span className="text-sm font-medium">{selected.nom}</span>
                    <div className="ml-auto flex items-center gap-1">
                      <Button size="sm" variant="ghost"
                        onClick={() => setFolderDlg({ mode: 'rename', folder: selected })}>
                        <Pencil className="size-4" aria-hidden="true" /> Renommer
                      </Button>
                      <Button size="sm" variant="ghost"
                        onClick={() => setFolderDlg({ mode: 'move', folder: selected })}>
                        <MoveRight className="size-4" aria-hidden="true" /> Déplacer
                      </Button>
                      {/* WIR70 — lien de dépôt public tokenisé pour ce dossier. */}
                      <Button size="sm" variant="ghost" onClick={createDepotLink}>
                        <Link2 className="size-4" aria-hidden="true" /> Lien de dépôt
                      </Button>
                      <Button size="sm" variant="default"
                        onClick={() => setUploadDlg(true)}>
                        <Upload className="size-4" aria-hidden="true" /> Téléverser
                      </Button>
                    </div>
                  </div>
                  {/* XGED14 — barre d'actions par lot (visible dès qu'une case est cochée). */}
                  {selectedIds.size > 0 && (
                    <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/40 px-4 py-2">
                      <span className="text-sm font-medium">
                        {selectedIds.size} sélectionné{selectedIds.size > 1 ? 's' : ''}
                      </span>
                      <div className="ml-auto flex items-center gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setSelectedIds(new Set())}>
                          Désélectionner
                        </Button>
                        <Button size="sm" variant="destructive"
                          onClick={bulkCorbeille} disabled={bulkBusy}>
                          {bulkBusy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Trash2 className="size-4" aria-hidden="true" />}
                          Mettre en corbeille
                        </Button>
                      </div>
                    </div>
                  )}
                  {loadingDocs ? (
                    <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
                      <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Chargement des documents…
                    </div>
                  ) : documents.length === 0 ? (
                    // U14 — état vide du dossier : CTA pour téléverser le premier document.
                    <EmptyState icon={Inbox}
                      title={`Dossier « ${selected.nom} »`}
                      description="Ce dossier ne contient aucun document. Téléversez-en un pour démarrer."
                      action={<Button onClick={() => setUploadDlg(true)}>
                        <Upload className="size-4" aria-hidden="true" /> Téléverser un document
                      </Button>} />
                  ) : (
                    <DataTable
                      data={documents}
                      columns={GED_DOC_COLUMNS}
                      getRowId={(d) => d.id}
                      manualSorting
                      manualFiltering
                      manualPagination
                      rowCount={documents.length}
                      pageSize={documents.length}
                      pageSizeOptions={[documents.length]}
                      searchable={false}
                      hideToolbar
                      hidePagination
                      tableRole="table"
                      aria-label="Documents du dossier"
                      renderHeaderRow={() => (
                        <>
                          <th scope="col" className="w-8">
                            {/* XGED14 — tout sélectionner. */}
                            <input type="checkbox"
                              aria-label="Tout sélectionner"
                              checked={selectedIds.size === documents.length && documents.length > 0}
                              onChange={toggleSelectAll} />
                          </th>
                          <th scope="col">Document</th>
                          <th scope="col" className="m-hide">Versions</th>
                          <th scope="col" className="m-hide">Créé par</th>
                          <th scope="col">Mis à jour</th>
                          <th scope="col" aria-label="Actions" />
                        </>
                      )}
                      renderRow={(d) => (
                        <tr key={d.id}>
                          <td data-label="" className="w-8">
                            <input type="checkbox"
                              aria-label={`Sélectionner ${d.nom}`}
                              checked={selectedIds.has(d.id)}
                              onChange={() => toggleSelect(d.id)} />
                          </td>
                          <td data-label="Document" className="font-medium">
                            {/* GED14 — clic sur le nom → aperçu du document. */}
                            <button type="button"
                              className="flex items-center gap-1.5 text-left hover:underline"
                              onClick={() => setPreviewDoc(d)}>
                              <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                              {d.nom}
                            </button>
                          </td>
                          <td data-label="Versions" className="m-hide">
                            {d.version_count ?? 0}
                            {d.derniere_version ? ` (v${d.derniere_version})` : ''}
                          </td>
                          <td data-label="Créé par" className="m-hide">
                            {d.created_by_nom || '—'}
                            {d.is_locked && (
                              <Badge tone="warning" className="ml-1.5 inline-flex items-center gap-0.5">
                                <Lock className="size-3" aria-hidden="true" />
                                {d.locked_by_nom ? d.locked_by_nom : 'extrait'}
                              </Badge>
                            )}
                          </td>
                          <td data-label="Mis à jour">{formatDate(d.updated_at)}</td>
                          <td data-label="Actions" className="text-right">
                            <div className="flex items-center justify-end gap-0.5">
                              <Button size="sm" variant="ghost"
                                aria-label={`Aperçu de ${d.nom}`}
                                onClick={() => setPreviewDoc(d)}>
                                <Eye className="size-4" aria-hidden="true" /> Aperçu
                              </Button>
                              {/* WIR70 — timeline + « qui voit ce document et pourquoi ». */}
                              <Button size="sm" variant="ghost"
                                aria-label={`Détails de ${d.nom}`}
                                onClick={() => setInsightsDoc(d)}>
                                <Info className="size-4" aria-hidden="true" /> Détails
                              </Button>
                              {d.is_locked ? (
                                <Button size="sm" variant="ghost"
                                  aria-label={`Archiver ${d.nom}`}
                                  onClick={() => checkIn(d)}>
                                  <LockOpen className="size-4" aria-hidden="true" /> Archiver
                                </Button>
                              ) : (
                                <Button size="sm" variant="ghost"
                                  aria-label={`Extraire ${d.nom}`}
                                  onClick={() => checkOut(d)}>
                                  <Lock className="size-4" aria-hidden="true" /> Extraire
                                </Button>
                              )}
                              <Button size="sm" variant="ghost"
                                aria-label={`Mettre ${d.nom} en corbeille`}
                                onClick={() => mettreEnCorbeille(d)}>
                                <Trash2 className="size-4" aria-hidden="true" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      )}
                    />
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── Dialogues d'écriture (U14) ── */}
      <CabinetDialog open={cabinetDlg} onOpenChange={setCabinetDlg}
        onCreated={onCabinetCreated} />
      <FolderDialog state={folderDlg} onClose={() => setFolderDlg(null)}
        cabinetId={cabinetId} folders={folders} onChanged={onFolderChanged} />
      <UploadDialog open={uploadDlg} onOpenChange={setUploadDlg}
        folder={selected} onUploaded={onDocumentUploaded} />
      <DocumentPreviewDialog document={previewDoc} onClose={() => setPreviewDoc(null)} />
      {/* WIR70 — panneau Détails (timeline + rapport ACL + favori). */}
      {insightsDoc && (
        <GedDocumentInsights document={insightsDoc} onClose={() => setInsightsDoc(null)} />
      )}
    </div>
  )
}

// ── GED14 — Aperçu inline d'un document (modale) ────────────────────────────
// Récupère les versions du document, prend la plus récente et l'affiche via le
// proxy même-origine (versions/<id>/apercu/). Dégrade proprement en lien de
// téléchargement si l'aperçu n'est pas disponible.
function DocumentPreviewDialog({ document: doc, onClose }) {
  const [version, setVersion] = useState(null)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!doc?.id) return
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture
    setLoading(true)
    setVersion(null)
    setFailed(false)
    gedApi.getVersions({ document: doc.id })
      .then((r) => {
        if (!alive) return
        const list = rows(r)
        const courante = [...list].sort((a, b) => (b.numero || 0) - (a.numero || 0))[0]
        if (courante) setVersion(courante)
        else setFailed(true)
      })
      .catch(() => { if (alive) setFailed(true) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [doc?.id])

  const src = version ? gedApi.apercuVersionUrl(version.id) : null
  const isImage = String(version?.mime || '').startsWith('image/')

  return (
    <Dialog open={!!doc} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="truncate">{doc?.nom || 'Aperçu'}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Chargement de l'aperçu…
          </div>
        ) : failed || !src ? (
          <p className="p-4 text-sm text-muted-foreground">
            L'aperçu de ce document n'est pas disponible.
          </p>
        ) : isImage ? (
          <img src={src} alt={`Aperçu de ${doc?.nom || 'document'}`}
            className="max-h-[70vh] w-full rounded border border-border object-contain" />
        ) : (
          <iframe title={`Aperçu de ${doc?.nom || 'document'}`} src={src}
            className="h-[70vh] w-full rounded border border-border" />
        )}
        <DialogFooter>
          {src && (
            <ExternalLink href={src}>
              <Button variant="outline">Ouvrir dans un onglet</Button>
            </ExternalLink>
          )}
          <DialogClose asChild>
            <Button variant="ghost">Fermer</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Dialogue : créer une armoire (cabinet) ──────────────────────────────
function CabinetDialog({ open, onOpenChange, onCreated }) {
  const [nom, setNom] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialiser le formulaire à l'ouverture du dialogue
    if (open) { setNom(''); setBusy(false) }
  }, [open])

  const submit = async (e) => {
    e.preventDefault()
    if (!nom.trim() || busy) return
    setBusy(true)
    try {
      const r = await gedApi.createCabinet({ nom: nom.trim() })
      toast.success('Armoire créée.')
      onOpenChange(false)
      onCreated?.(r.data)
    } catch (err) {
      toast.error(errText(err, "Impossible de créer l'armoire."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle armoire</DialogTitle>
          <DialogDescription>
            Une armoire (cabinet) est la racine d'une arborescence documentaire.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <Input aria-label="Nom de l'armoire" placeholder="Ex. Administratif"
            value={nom} onChange={(e) => setNom(e.target.value)} autoFocus />
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="ghost">Annuler</Button>
            </DialogClose>
            <Button type="submit" disabled={!nom.trim() || busy}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Créer l'armoire
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Dialogue : créer / renommer / déplacer un dossier ───────────────────
function FolderDialog({ state, onClose, cabinetId, folders, onChanged }) {
  const mode = state?.mode
  const target = state?.folder
  const [nom, setNom] = useState('')
  const [parentId, setParentId] = useState('') // '' = racine ; sinon id (string)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!state) return
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialiser le formulaire à l'ouverture du dialogue
    setBusy(false)
    setNom(mode === 'rename' ? (target?.nom ?? '') : '')
    setParentId(
      mode === 'move'
        ? (target?.parent != null ? String(target.parent) : '')
        : '',
    )
  }, [state, mode, target])

  // Parents possibles : tous les dossiers du cabinet, en EXCLUANT (pour un
  // déplacement) le dossier déplacé et son sous-arbre (le backend refuse les
  // cycles, mais on filtre aussi côté UI pour un choix propre).
  const parentOptions = useMemo(() => {
    const list = Array.isArray(folders) ? folders : []
    if (mode !== 'move' || !target) return list
    const banned = list.filter(
      (f) => typeof f.path === 'string' && typeof target.path === 'string'
        && f.path.startsWith(target.path),
    ).map((f) => f.id)
    const bannedSet = new Set([target.id, ...banned])
    return list.filter((f) => !bannedSet.has(f.id))
  }, [folders, mode, target])

  const titles = {
    create: 'Nouveau dossier',
    rename: 'Renommer le dossier',
    move: 'Déplacer le dossier',
  }

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    if ((mode === 'create' || mode === 'rename') && !nom.trim()) return
    setBusy(true)
    try {
      if (mode === 'create') {
        const body = { cabinet: cabinetId, nom: nom.trim() }
        if (parentId) body.parent = Number(parentId)
        await gedApi.createDossier(body)
        toast.success('Dossier créé.')
      } else if (mode === 'rename') {
        await gedApi.renameDossier(target.id, nom.trim())
        toast.success('Dossier renommé.')
      } else if (mode === 'move') {
        await gedApi.moveDossier(target.id, parentId ? Number(parentId) : null)
        toast.success('Dossier déplacé.')
      }
      onClose()
      onChanged?.()
    } catch (err) {
      toast.error(errText(err, "Action impossible sur le dossier."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={!!state} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titles[mode] || 'Dossier'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          {(mode === 'create' || mode === 'rename') && (
            <Input aria-label="Nom du dossier" placeholder="Ex. Contrats"
              value={nom} onChange={(e) => setNom(e.target.value)} autoFocus />
          )}
          {(mode === 'create' || mode === 'move') && (
            <label className="grid gap-1 text-sm">
              <span className="text-muted-foreground">Dossier parent (optionnel)</span>
              <Select value={parentId} onValueChange={(v) => setParentId(v === '__root__' ? '' : v)}>
                <SelectTrigger aria-label="Dossier parent">
                  <SelectValue placeholder="— Racine de l'armoire —" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__root__">— Racine de l'armoire —</SelectItem>
                  {parentOptions.map((f) => (
                    <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="ghost">Annuler</Button>
            </DialogClose>
            <Button type="submit"
              disabled={busy || ((mode === 'create' || mode === 'rename') && !nom.trim())}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Valider
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Dialogue : téléverser un document ───────────────────────────────────
function UploadDialog({ open, onOpenChange, folder, onUploaded }) {
  const [file, setFile] = useState(null)
  const [nom, setNom] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialiser le formulaire à l'ouverture du dialogue
    if (open) { setFile(null); setNom(''); setDescription(''); setBusy(false) }
  }, [open])

  const submit = async (e) => {
    e.preventDefault()
    if (!file || !folder || busy) return
    setBusy(true)
    try {
      await gedApi.uploadDocument({
        folder: folder.id, file, nom: nom.trim(), description: description.trim(),
      })
      toast.success('Document téléversé.')
      onOpenChange(false)
      onUploaded?.()
    } catch (err) {
      toast.error(errText(err, 'Téléversement impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Téléverser un document</DialogTitle>
          <DialogDescription>
            {folder ? `Dans le dossier « ${folder.nom} ».` : null}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="grid gap-3">
          <FileUpload accept="application/pdf,image/png,image/jpeg,image/webp"
            maxSize={10 * 1024 * 1024}
            onFiles={(files) => { setFile(files[0]); if (!nom) setNom(files[0]?.name || '') }}
            onReject={(rej) => toast.error(rej[0]?.error || 'Fichier refusé.')} />
          {file && (
            <p className="text-sm text-muted-foreground">
              Fichier sélectionné : <span className="font-medium text-foreground">{file.name}</span>
            </p>
          )}
          <Input aria-label="Nom du document"
            placeholder="Nom du document (par défaut : nom du fichier)"
            value={nom} onChange={(e) => setNom(e.target.value)} />
          <Textarea aria-label="Description" rows={2}
            placeholder="Description (optionnel)"
            value={description} onChange={(e) => setDescription(e.target.value)} />
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="ghost">Annuler</Button>
            </DialogClose>
            <Button type="submit" disabled={!file || busy}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
              Téléverser
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
