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
  Trash2, Info, Link2, EyeOff, X, Archive, Tag as TagIcon, Undo2, Settings2,
} from 'lucide-react'
import gedApi from '../../api/gedApi'
// WIR204 — un ZIP de lot / un PDF signé arrivent en BINAIRE : la remise passe
// par le helper commun (pré-ouverture d'onglet iOS/PWA incluse), jamais par un
// `<a download>` ad hoc.
import { downloadBlobInGesture } from '../../utils/downloadBlob'
// APX32 (e) — en-tête UNIQUE de l'app (VX28), fin du 4ᵉ idiome.
import { PageHeader } from '../../ui/PageHeader'
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
  // XGED10 — fusion de plusieurs PDF sélectionnés (dialogue de confirmation).
  const [mergeDlg, setMergeDlg] = useState(false)
  // WIR204/XGED14 — dialogue d'opération de lot ('tagger'|'detaguer'|'deplacer').
  const [bulkDlg, setBulkDlg] = useState(null)
  const [tags, setTags] = useState([])
  // WIR249 — actions de second rang d'UN document (OCR pièce, verrou
  // d'avertissement ZGED9, cycle de vie GED17, éditeur Office XGED30).
  const [advancedDoc, setAdvancedDoc] = useState(null)

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

  // WIR204 — taxonomie de tags (GED9), nécessaire aux opérations de lot
  // tagger/détaguer. Chargée une fois : une liste vide désactive l'action au
  // lieu de proposer un formulaire qui ne peut rien envoyer.
  useEffect(() => {
    let alive = true
    gedApi.getTags()
      .then((r) => { if (alive) setTags(rows(r)) })
      .catch(() => { if (alive) setTags([]) })
    return () => { alive = false }
  }, [])

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

  // WIR204/XGED14 — le ZIP est le SEUL retour BINAIRE d'`operations-lot` : il
  // passe par un wrapper blob DÉDIÉ (l'appel générique JSON corrompait
  // l'archive), avec pré-ouverture d'onglet dans le geste de clic.
  const bulkZip = async () => {
    if (selectedIds.size === 0) return
    const pending = downloadBlobInGesture()
    setBulkBusy(true)
    try {
      const res = await gedApi.telechargerZipLot([...selectedIds])
      pending.deliver(res.data, 'documents.zip')
      toast.success(`${selectedIds.size} document(s) dans l'archive.`)
    } catch (err) {
      toast.error(errText(err, 'Téléchargement du ZIP impossible.'))
    } finally { setBulkBusy(false) }
  }

  // WIR204/XGED14 — tagger / détaguer / déplacer par lot. Le serveur valide
  // CHAQUE document séparément : un item bloqué (archivé, hold légal) revient
  // dans `erreurs` — on le DIT, on ne le tait jamais derrière un succès global.
  const bulkOperation = async (operation, params, labelSucces) => {
    if (selectedIds.size === 0) return
    setBulkBusy(true)
    try {
      const res = await gedApi.operationsLot({
        documents: [...selectedIds], operation, params,
      })
      const erreurs = res?.data?.erreurs || []
      const resultats = res?.data?.resultats || []
      if (erreurs.length) {
        toast.error(`${erreurs.length} document(s) non traité(s) : `
          + `${erreurs.map((e) => e.erreur).filter(Boolean).join(' · ')}`)
      }
      if (resultats.length) toast.success(`${resultats.length} ${labelSucces}`)
      setBulkDlg(null)
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
      {/* APX32 (e) — 4ᵉ idiome d'en-tête du repo (`<h1>` nu + `<p>` en taille
          arbitraire) : l'en-tête UNIQUE de l'app (VX28). */}
      <PageHeader
        className="mb-4"
        icon={Folder}
        title="Documents (GED)"
        subtitle="Arborescence documentaire — créez une armoire et un dossier, puis téléversez vos documents."
        actions={(
          <>
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
          </>
        )}
      />

      {/* GED13 — Filtres & recherche avancée (plein-texte/sémantique + tags).
          ZGED7/13 — favoris/récents ouvrent l'aperçu inline GED14. */}
      <div className="mb-4">
        <GedSearch onOpenDocument={setPreviewDoc} />
      </div>

      {/* WIR249/FG352 — DocQA : poser une QUESTION et recevoir les extraits qui
          y répondent (GED + base de connaissances). KEY-GATED : sans clé
          d'embedding, le serveur renvoie `enabled:false` — on l'écrit, on ne
          simule jamais une réponse. */}
      <DocQaPanel />


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
                        {/* XGED10 — fusionne les PDF sélectionnés (≥2) en un seul document. */}
                        {selectedIds.size >= 2 && (
                          <Button size="sm" variant="outline" onClick={() => setMergeDlg(true)}>
                            <FileText className="size-4" aria-hidden="true" /> Fusionner
                          </Button>
                        )}
                        {/* WIR204/XGED14 — archive ZIP de la sélection (blob dédié). */}
                        <Button size="sm" variant="outline" data-testid="ged-bulk-zip"
                          onClick={bulkZip} disabled={bulkBusy}>
                          <Archive className="size-4" aria-hidden="true" /> Télécharger (ZIP)
                        </Button>
                        {/* WIR204/XGED14 — tagger / détaguer / déplacer par lot. */}
                        <Button size="sm" variant="outline" data-testid="ged-bulk-tag"
                          onClick={() => setBulkDlg('tagger')} disabled={bulkBusy || tags.length === 0}>
                          <TagIcon className="size-4" aria-hidden="true" /> Tagger
                        </Button>
                        <Button size="sm" variant="outline" data-testid="ged-bulk-untag"
                          onClick={() => setBulkDlg('detaguer')} disabled={bulkBusy || tags.length === 0}>
                          <TagIcon className="size-4" aria-hidden="true" /> Détaguer
                        </Button>
                        <Button size="sm" variant="outline" data-testid="ged-bulk-move"
                          onClick={() => setBulkDlg('deplacer')} disabled={bulkBusy || folders.length === 0}>
                          <MoveRight className="size-4" aria-hidden="true" /> Déplacer
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
                              {/* WIR249 — surfaces de second rang (OCR pièce,
                                  verrou d'AVERTISSEMENT ZGED9 distinct du
                                  check-out, cycle de vie GED17, éditeur
                                  Office) : regroupées, jamais un 6ᵉ bouton. */}
                              <Button size="sm" variant="ghost"
                                aria-label={`Actions avancées sur ${d.nom}`}
                                data-testid={`ged-avance-${d.id}`}
                                onClick={() => setAdvancedDoc(d)}>
                                <Settings2 className="size-4" aria-hidden="true" />
                              </Button>
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
      <DocumentPreviewDialog document={previewDoc} onClose={() => setPreviewDoc(null)}
        onCaviarde={reloadDocuments} />
      {/* WIR249 — actions de second rang sur un document. */}
      {advancedDoc && (
        <DocumentAdvancedDialog document={advancedDoc}
          onClose={() => setAdvancedDoc(null)} onChanged={reloadDocuments} />
      )}
      {/* WIR204/XGED14 — tagger / détaguer / déplacer la sélection. */}
      {bulkDlg && (
        <BulkOperationDialog
          operation={bulkDlg} count={selectedIds.size} tags={tags} folders={folders}
          busy={bulkBusy} onClose={() => setBulkDlg(null)}
          onSubmit={(params) => bulkOperation(
            bulkDlg, params,
            bulkDlg === 'deplacer' ? 'document(s) déplacé(s).'
              : bulkDlg === 'tagger' ? 'document(s) taggé(s).'
                : 'document(s) détaggé(s).')} />
      )}
      {/* XGED10 — fusion des documents sélectionnés (bordure de la barre en lot). */}
      {mergeDlg && (
        <MergeDocumentsDialog
          documents={documents.filter((d) => selectedIds.has(d.id))}
          onClose={() => setMergeDlg(false)}
          onDone={() => { setMergeDlg(false); setSelectedIds(new Set()); reloadDocuments() }}
        />
      )}
      {/* WIR70 — panneau Détails (timeline + rapport ACL + favori). */}
      {insightsDoc && (
        <GedDocumentInsights document={insightsDoc} onClose={() => setInsightsDoc(null)} />
      )}
    </div>
  )
}

// ── WIR249/FG352 — DocQA : poser une question, lire les extraits ────────────
// `GET documents/docqa/?q=&k=` renvoie `{enabled, results}` où chaque résultat
// vient de la GED (`document_nom`) OU de la base de connaissances
// (`article_titre`). KEY-GATED : `enabled:false` = aucune clé d'embedding
// configurée — l'écran le DIT plutôt que d'afficher un vide qui ment.
function DocQaPanel() {
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [reponse, setReponse] = useState(null)

  const ask = async () => {
    const question = q.trim()
    if (!question) return
    setBusy(true)
    try {
      const r = await gedApi.docqa(question, 5)
      setReponse({
        enabled: r?.data?.enabled !== false,
        results: Array.isArray(r?.data?.results) ? r.data.results : [],
      })
    } catch (err) {
      toast.error(errText(err, 'Recherche de réponse impossible.'))
    } finally { setBusy(false) }
  }

  return (
    <Card className="mb-4">
      <CardContent className="flex flex-col gap-2 p-4">
        <div className="flex items-end gap-2">
          <Input className="flex-1" aria-label="Question sur vos documents"
            data-testid="ged-docqa-q" placeholder="Poser une question sur vos documents…"
            value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') ask() }} />
          <Button type="button" onClick={ask} disabled={busy || !q.trim()}
            data-testid="ged-docqa-ask">
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            Chercher la réponse
          </Button>
        </div>
        {reponse && !reponse.enabled && (
          <p className="text-[12.5px] text-muted-foreground" data-testid="ged-docqa-disabled">
            La recherche par question n&apos;est pas activée sur cette installation
            (aucune clé d&apos;indexation sémantique configurée).
          </p>
        )}
        {reponse?.enabled && reponse.results.length === 0 && (
          <p className="text-[12.5px] text-muted-foreground" data-testid="ged-docqa-empty">
            Aucun extrait ne répond à cette question.
          </p>
        )}
        {reponse?.enabled && reponse.results.length > 0 && (
          <ul className="grid gap-2" data-testid="ged-docqa-results">
            {reponse.results.map((r, i) => (
              <li key={`${r.source}-${r.document ?? r.article}-${r.chunk_index}-${i}`}
                data-testid="ged-docqa-result"
                className="rounded border border-border p-2 text-[12.5px]">
                <strong>{r.document_nom || r.article_titre || 'Extrait'}</strong>
                <span className="ml-1 text-muted-foreground">
                  ({r.source === 'kb' ? 'base de connaissances' : 'GED'})
                </span>
                <p className="mt-0.5 text-muted-foreground">{r.texte}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

// ── WIR249 — Actions de SECOND RANG sur un document ─────────────────────────
// Quatre surfaces exposées par le backend mais sans aucun appelant :
//  * GED33 `ocr-piece` — OCR d'une pièce → métadonnées typées, fusion ADDITIVE ;
//  * ZGED9 `verrouiller`/`deverrouiller` — verrou d'AVERTISSEMENT, DISTINCT du
//    check-out GED16 (il n'empêche jamais la lecture, il prévient) ;
//  * GED17 `cycle-vie` — statut documentaire LOCAL (sans rapport avec STAGES.py),
//    transitions gardées côté serveur (400 explicite si interdite) ;
//  * XGED30 `office-ouvrir` — éditeur Office embarqué, KEY-GATED (400 sans URL).
const TYPES_PIECE = [
  { value: '', label: 'Deviner le type' },
  { value: 'cin', label: 'CIN' },
  { value: 'facture', label: 'Facture' },
  { value: 'bl', label: 'Bon de livraison' },
]
// GED17 — cibles possibles ; le serveur reste seul juge de la transition.
const CYCLE_VIE = [
  { value: 'brouillon', label: 'Brouillon' },
  { value: 'revue', label: 'En revue' },
  { value: 'approuve', label: 'Approuvé' },
  { value: 'archive', label: 'Archivé' },
  { value: 'obsolete', label: 'Obsolète' },
]

function DocumentAdvancedDialog({ document: doc, onClose, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [typePiece, setTypePiece] = useState('')
  const [statut, setStatut] = useState(doc.statut || 'brouillon')
  const [motif, setMotif] = useState('')
  const verrouille = !!(doc.est_verrouille_avertissement
    || doc.verrou_avertissement_par)

  const run = async (fn, succes) => {
    setBusy(true)
    try {
      await fn()
      toast.success(succes)
      onChanged?.()
      onClose()
    } catch (err) {
      // 409 = verrou déjà posé par un autre ; 400 = transition interdite ou
      // éditeur Office non configuré : le message du serveur est le bon.
      toast.error(errText(err, 'Action impossible.'))
    } finally { setBusy(false) }
  }

  const ouvrirOffice = async () => {
    setBusy(true)
    try {
      const r = await gedApi.officeOuvrirDocument(doc.id)
      const url = r?.data?.editor_url
      if (url) { window.open(url, '_blank', 'noopener'); onChanged?.(); onClose() }
      else toast.error("L'éditeur Office n'a pas renvoyé d'adresse.")
    } catch (err) {
      toast.error(errText(err, "Éditeur Office indisponible sur cette installation."))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="truncate">Actions avancées — {doc.nom}</DialogTitle>
          <DialogDescription>
            Le verrou d&apos;avertissement n&apos;empêche jamais la lecture : il prévient
            les collègues. Il est distinct de l&apos;extraction (check-out).
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          {/* GED33 — OCR d'une pièce. */}
          <div className="flex items-end gap-2">
            <div className="grid flex-1 gap-1">
              <span className="text-xs text-muted-foreground">Type de pièce</span>
              <Select value={typePiece} onValueChange={setTypePiece}>
                <SelectTrigger aria-label="Type de pièce" data-testid="ged-ocr-type">
                  <SelectValue placeholder="Deviner le type" />
                </SelectTrigger>
                <SelectContent>
                  {TYPES_PIECE.filter((t) => t.value).map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="button" disabled={busy} data-testid="ged-ocr-piece"
              onClick={() => run(
                () => gedApi.ocrPieceDocument(doc.id, typePiece || undefined),
                'Métadonnées extraites et ajoutées.')}>
              Lire la pièce (OCR)
            </Button>
          </div>

          {/* ZGED9 — verrou d'AVERTISSEMENT (distinct du check-out GED16). */}
          <div className="flex items-end gap-2">
            {verrouille ? (
              <Button type="button" variant="outline" disabled={busy}
                data-testid="ged-deverrouiller"
                onClick={() => run(() => gedApi.deverrouillerDocument(doc.id),
                  'Verrou d’avertissement levé.')}>
                <LockOpen className="size-4" aria-hidden="true" /> Lever l&apos;avertissement
              </Button>
            ) : (<>
              <Input className="flex-1" aria-label="Motif du verrou"
                data-testid="ged-verrou-motif" placeholder="Motif (optionnel)"
                value={motif} onChange={(e) => setMotif(e.target.value)} />
              <Button type="button" variant="outline" disabled={busy}
                data-testid="ged-verrouiller"
                onClick={() => run(() => gedApi.verrouillerDocument(doc.id, motif),
                  'Avertissement « en cours d’édition » posé.')}>
                <Lock className="size-4" aria-hidden="true" /> Signaler « en cours d&apos;édition »
              </Button>
            </>)}
          </div>

          {/* GED17 — cycle de vie documentaire. */}
          <div className="flex items-end gap-2">
            <div className="grid flex-1 gap-1">
              <span className="text-xs text-muted-foreground">Statut du cycle de vie</span>
              <Select value={statut} onValueChange={setStatut}>
                <SelectTrigger aria-label="Statut du cycle de vie"
                  data-testid="ged-cycle-statut"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CYCLE_VIE.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="button" disabled={busy} data-testid="ged-cycle-vie"
              onClick={() => run(
                () => gedApi.changerCycleVieDocument(doc.id, statut),
                'Statut du cycle de vie mis à jour.')}>
              Appliquer
            </Button>
          </div>

          {/* XGED30 — éditeur Office embarqué (key-gated : 400 sans URL). */}
          <Button type="button" variant="outline" disabled={busy}
            data-testid="ged-office-ouvrir" onClick={ouvrirOffice}>
            Ouvrir dans l&apos;éditeur Office
          </Button>
        </div>

        <DialogFooter>
          <DialogClose asChild><Button variant="ghost">Fermer</Button></DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── WIR204/XGED14 — Opération de lot paramétrée (tagger/détaguer/déplacer) ──
// Le serveur valide CHAQUE document séparément : le rapport `erreurs` est
// remonté tel quel par l'appelant — jamais un « tout s'est bien passé » global.
function BulkOperationDialog({ operation, count, tags, folders, busy, onClose, onSubmit }) {
  const isMove = operation === 'deplacer'
  const options = isMove ? folders : tags
  const [value, setValue] = useState(String(options[0]?.id ?? ''))
  const titres = {
    tagger: 'Tagger la sélection',
    detaguer: 'Détaguer la sélection',
    deplacer: 'Déplacer la sélection',
  }
  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titres[operation] || 'Opération en lot'}</DialogTitle>
          <DialogDescription>
            {count} document(s) sélectionné(s). Chaque document est traité
            individuellement : ceux qui sont bloqués (archivés, conservation
            légale) seront listés à part.
          </DialogDescription>
        </DialogHeader>
        <Select value={value} onValueChange={setValue}>
          <SelectTrigger aria-label={isMove ? 'Dossier cible' : 'Tag'}
            data-testid="ged-bulk-target"><SelectValue /></SelectTrigger>
          <SelectContent>
            {options.map((o) => (
              <SelectItem key={o.id} value={String(o.id)}>{o.nom}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <DialogFooter>
          <DialogClose asChild><Button variant="ghost">Annuler</Button></DialogClose>
          <Button type="button" disabled={busy || !value} data-testid="ged-bulk-confirm"
            onClick={() => onSubmit(isMove ? { folder: value } : { tag: value })}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />} Confirmer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── GED14 — Aperçu inline d'un document (modale) ────────────────────────────
// Récupère les versions du document, prend la plus récente et l'affiche via le
// proxy même-origine (versions/<id>/apercu/). Dégrade proprement en lien de
// téléchargement si l'aperçu n'est pas disponible.
function DocumentPreviewDialog({ document: doc, onClose, onCaviarde }) {
  const [version, setVersion] = useState(null)
  // XGED17 — toutes les versions (pour le comparateur), pas seulement la
  // plus récente affichée dans l'aperçu.
  const [allVersions, setAllVersions] = useState([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  // XGED24 — caviardage (rédaction) de zones, PDF uniquement.
  const [redactOpen, setRedactOpen] = useState(false)
  // XGED10 — scission en segments, PDF uniquement.
  const [splitOpen, setSplitOpen] = useState(false)
  // XGED17 — comparateur de versions.
  const [compareOpen, setCompareOpen] = useState(false)

  useEffect(() => {
    if (!doc?.id) return
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture
    setLoading(true)
    setVersion(null)
    setAllVersions([])
    setFailed(false)
    gedApi.getVersions({ document: doc.id })
      .then((r) => {
        if (!alive) return
        const list = rows(r)
        setAllVersions(list)
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
  const isPdf = String(version?.mime || '') === 'application/pdf'

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
          {/* XGED10 — scinder ce PDF en segments (nouveaux documents). */}
          {isPdf && (
            <Button variant="outline" onClick={() => setSplitOpen(true)}>
              Scinder…
            </Button>
          )}
          {/* XGED17 — comparer deux versions de ce document. */}
          {allVersions.length > 1 && (
            <Button variant="outline" onClick={() => setCompareOpen(true)}>
              Comparer versions…
            </Button>
          )}
          {/* XGED24 — caviarder une COPIE (PDF uniquement, l'original n'est
              jamais modifié). */}
          {isPdf && (
            <Button variant="outline" onClick={() => setRedactOpen(true)}>
              <EyeOff /> Caviarder…
            </Button>
          )}
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
      {redactOpen && (
        <RedactZonesDialog
          documentId={doc.id}
          versionId={version?.id}
          onClose={() => setRedactOpen(false)}
          onDone={() => { setRedactOpen(false); onClose(); onCaviarde?.() }}
        />
      )}
      {splitOpen && (
        <SplitDocumentDialog
          documentId={doc.id}
          versionId={version?.id}
          onClose={() => setSplitOpen(false)}
          onDone={() => { setSplitOpen(false); onClose(); onCaviarde?.() }}
        />
      )}
      {compareOpen && (
        <CompareVersionsDialog
          documentId={doc.id}
          versions={allVersions}
          onClose={() => setCompareOpen(false)}
          onRestored={() => { onClose(); onCaviarde?.() }}
        />
      )}
    </Dialog>
  )
}

// ── XGED24 — Dialogue : zones à caviarder (rédaction PDF, copie publiée) ───
// Chaque zone : { page (0-based), x0, y0, x1, y1 } en POURCENTAGE (0-100) de
// la page (même convention que les annotations XGED16). Le texte sous la
// zone est SUPPRIMÉ côté serveur (PyMuPDF) — jamais un simple rectangle
// visuel — sur une COPIE ; l'original n'est jamais modifié.
const EMPTY_ZONE = { page: '0', x0: '0', y0: '0', x1: '20', y1: '10' }

function RedactZonesDialog({ documentId, versionId, onClose, onDone }) {
  const [zones, setZones] = useState([{ ...EMPTY_ZONE }])
  const [busy, setBusy] = useState(false)

  const updateZone = (i, field, value) =>
    setZones((prev) => prev.map((z, idx) => (idx === i ? { ...z, [field]: value } : z)))
  const addZone = () => setZones((prev) => [...prev, { ...EMPTY_ZONE }])
  const removeZone = (i) => setZones((prev) => prev.filter((_, idx) => idx !== i))

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      const payload = zones.map((z) => ({
        page: Number(z.page) || 0,
        x0: Number(z.x0) || 0, y0: Number(z.y0) || 0,
        x1: Number(z.x1) || 0, y1: Number(z.y1) || 0,
      }))
      await gedApi.caviarderDocument(documentId, { zones: payload, version: versionId })
      toast.success('Copie caviardée créée dans le dossier.')
      onDone()
    } catch (err) {
      toast.error(errText(err, 'Caviardage impossible.'))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Caviarder ce document</DialogTitle>
          <DialogDescription>
            Une COPIE est créée avec les zones ci-dessous définitivement noircies
            (texte supprimé) ; l&apos;original reste intact. Coordonnées en % de
            la page (page 0 = première page).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3">
          {zones.map((z, i) => (
            <div key={i} className="flex items-end gap-1.5">
              <div className="flex flex-col gap-0.5">
                <label className="text-xs text-muted-foreground" htmlFor={`z-page-${i}`}>Page</label>
                <Input id={`z-page-${i}`} type="number" min={0} className="w-16"
                  value={z.page} onChange={(e) => updateZone(i, 'page', e.target.value)} />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className="text-xs text-muted-foreground" htmlFor={`z-x0-${i}`}>X0 %</label>
                <Input id={`z-x0-${i}`} type="number" min={0} max={100} className="w-16"
                  value={z.x0} onChange={(e) => updateZone(i, 'x0', e.target.value)} />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className="text-xs text-muted-foreground" htmlFor={`z-y0-${i}`}>Y0 %</label>
                <Input id={`z-y0-${i}`} type="number" min={0} max={100} className="w-16"
                  value={z.y0} onChange={(e) => updateZone(i, 'y0', e.target.value)} />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className="text-xs text-muted-foreground" htmlFor={`z-x1-${i}`}>X1 %</label>
                <Input id={`z-x1-${i}`} type="number" min={0} max={100} className="w-16"
                  value={z.x1} onChange={(e) => updateZone(i, 'x1', e.target.value)} />
              </div>
              <div className="flex flex-col gap-0.5">
                <label className="text-xs text-muted-foreground" htmlFor={`z-y1-${i}`}>Y1 %</label>
                <Input id={`z-y1-${i}`} type="number" min={0} max={100} className="w-16"
                  value={z.y1} onChange={(e) => updateZone(i, 'y1', e.target.value)} />
              </div>
              {zones.length > 1 && (
                <Button type="button" variant="ghost" size="sm"
                  aria-label="Retirer cette zone" onClick={() => removeZone(i)}>
                  <X size={14} />
                </Button>
              )}
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" className="self-start" onClick={addZone}>
            <Plus /> Ajouter une zone
          </Button>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <EyeOff />} Caviarder
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── XGED10 — Dialogue : scinder un PDF en segments ──────────────────────────
// `pointsDeCoupe` : numéros de page 1-based où commence chaque nouveau
// segment (ex. "1,3" sur un PDF de 6 pages → [1-2] puis [3-6]).
function SplitDocumentDialog({ documentId, versionId, onClose, onDone }) {
  const [points, setPoints] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    const pointsDeCoupe = points.split(',').map((p) => p.trim()).filter(Boolean).map(Number)
    if (pointsDeCoupe.length === 0 || pointsDeCoupe.some((p) => !Number.isInteger(p) || p < 1)) {
      toast.error('Indiquez au moins un numéro de page (entiers ≥ 1) séparés par des virgules.')
      return
    }
    setBusy(true)
    try {
      await gedApi.scinderDocument(documentId, { pointsDeCoupe, version: versionId })
      toast.success('Document scindé en segments.')
      onDone()
    } catch (err) {
      toast.error(errText(err, 'Scission impossible.'))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Scinder ce document</DialogTitle>
          <DialogDescription>
            Chaque segment devient un nouveau document ; l&apos;original reste
            intact. Indiquez les numéros de PAGE (1 = première page) où
            commence chaque nouveau segment, séparés par des virgules
            (ex. « 1, 3 » sur un PDF de 6 pages donne [1-2] et [3-6]).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-sm text-muted-foreground" htmlFor="split-points">
              Points de coupe
            </label>
            <Input id="split-points" placeholder="1, 3"
              value={points} onChange={(e) => setPoints(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />} Scinder
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── XGED17 — Dialogue : comparer deux versions d'un document ───────────────
function CompareVersionsDialog({ documentId, versions, onClose, onRestored }) {
  const sorted = [...versions].sort((a, b) => (b.numero || 0) - (a.numero || 0))
  const [v1, setV1] = useState(String(sorted[1]?.id ?? sorted[0]?.id ?? ''))
  const [v2, setV2] = useState(String(sorted[0]?.id ?? ''))
  const [diff, setDiff] = useState(null)
  const [busy, setBusy] = useState(false)
  // WIR204/GED15 — restauration d'une version antérieure. Opération ADDITIVE :
  // le serveur crée une NOUVELLE version copiée depuis la source, l'historique
  // reste entier (rien n'est écrasé ni supprimé).
  const [restoreBusy, setRestoreBusy] = useState(false)
  const restaurer = async () => {
    if (!v1) return
    setRestoreBusy(true)
    try {
      await gedApi.restaurerVersionDocument(documentId, v1)
      toast.success('Version restaurée : une nouvelle version a été créée.')
      onRestored?.()
      onClose()
    } catch (err) {
      toast.error(errText(err, 'Restauration de version impossible.'))
    } finally { setRestoreBusy(false) }
  }

  const compare = async () => {
    if (!v1 || !v2) return
    setBusy(true)
    try {
      const r = await gedApi.comparerVersions(documentId, v1, v2)
      setDiff(r.data)
    } catch (err) {
      toast.error(errText(err, 'Comparaison impossible.'))
    } finally { setBusy(false) }
  }

  const metaEntries = diff?.metadonnees ? Object.entries(diff.metadonnees) : []

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Comparer deux versions</DialogTitle>
        </DialogHeader>
        <div className="flex items-end gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground" htmlFor="cmp-v1">Version A</label>
            <Select value={v1} onValueChange={setV1}>
              <SelectTrigger id="cmp-v1" aria-label="Version A" className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                {sorted.map((v) => (
                  <SelectItem key={v.id} value={String(v.id)}>v{v.numero}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground" htmlFor="cmp-v2">Version B</label>
            <Select value={v2} onValueChange={setV2}>
              <SelectTrigger id="cmp-v2" aria-label="Version B" className="w-32"><SelectValue /></SelectTrigger>
              <SelectContent>
                {sorted.map((v) => (
                  <SelectItem key={v.id} value={String(v.id)}>v{v.numero}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="button" onClick={compare} disabled={busy || v1 === v2}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />} Comparer
          </Button>
          {/* WIR204/GED15 — restaurer la version A (additif, jamais destructif). */}
          <Button type="button" variant="outline" data-testid="ged-restaurer-version"
            onClick={restaurer} disabled={restoreBusy || !v1}>
            {restoreBusy
              ? <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              : <Undo2 className="size-4" aria-hidden="true" />}
            Restaurer la version A
          </Button>
        </div>
        {diff && (
          <div className="mt-3 flex flex-col gap-3">
            {metaEntries.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune différence de métadonnées.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th>Champ</th><th>Version A</th><th>Version B</th>
                  </tr>
                </thead>
                <tbody>
                  {metaEntries.map(([champ, { v1: a, v2: b }]) => (
                    <tr key={champ} className="border-t border-border">
                      <td className="py-1 font-medium">{champ}</td>
                      <td className="py-1">{String(a ?? '—')}</td>
                      <td className="py-1">{String(b ?? '—')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {diff.texte_disponible ? (
              <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/40 p-2 text-xs">
                {(diff.diff_texte || []).join('\n')}
              </pre>
            ) : (
              <p className="text-xs text-muted-foreground">{diff.message}</p>
            )}
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── XGED10 — Dialogue : fusionner les documents sélectionnés en un seul PDF ─
// L'ordre de fusion suit l'ordre de sélection (Set → insertion order). Un
// nouveau document est créé dans le dossier du 1er document source ; les
// sources ne sont jamais modifiées.
function MergeDocumentsDialog({ documents, onClose, onDone }) {
  const [nom, setNom] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      await gedApi.fusionnerDocuments({
        documents: documents.map((d) => d.id), nom: nom.trim() || undefined,
      })
      toast.success('Documents fusionnés.')
      onDone()
    } catch (err) {
      toast.error(errText(err, 'Fusion impossible.'))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Fusionner {documents.length} documents</DialogTitle>
          <DialogDescription>
            Un nouveau document PDF est créé, dans l&apos;ordre ci-dessous. Les
            documents sources restent intacts.
          </DialogDescription>
        </DialogHeader>
        <ol className="flex flex-col gap-1 text-sm">
          {documents.map((d, i) => (
            <li key={d.id} className="rounded-md border px-2 py-1">
              {i + 1}. {d.nom}
            </li>
          ))}
        </ol>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-sm text-muted-foreground" htmlFor="merge-nom">
              Nom du document fusionné (optionnel)
            </label>
            <Input id="merge-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />} Fusionner
            </Button>
          </DialogFooter>
        </form>
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
