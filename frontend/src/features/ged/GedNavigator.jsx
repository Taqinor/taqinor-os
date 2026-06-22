// GED5 — Navigateur arborescent (frontend). Vue en arbre des dossiers (GED) avec
// dépliage/repliage, et liste des documents du dossier sélectionné. Consomme les
// endpoints existants d'`apps/ged` (cabinets / dossiers / documents) — aucun
// modèle backend ajouté. Tout le texte est en français, lecture seule.
import { useEffect, useMemo, useState } from 'react'
import {
  Folder, FolderOpen, ChevronRight, ChevronDown, FileText, Loader2, Inbox,
  RefreshCw,
} from 'lucide-react'
import gedApi from '../../api/gedApi'
import { formatDate } from '../../lib/format'
import {
  Card, CardContent, Button, EmptyState, Skeleton, Badge,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { buildFolderTree, flattenVisible, countFolders } from './tree.js'

// Le backend pagine certains endpoints (DRF) : on accepte `results` OU le
// tableau brut, comme partout dans le frontend.
const rows = (r) => r?.data?.results ?? r?.data ?? []

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

  // ── Chargement des cabinets (armoires racines) ──
  useEffect(() => {
    let alive = true
    gedApi.getCabinets()
      .then((r) => {
        if (!alive) return
        const list = rows(r)
        setCabinets(list)
        // Sélectionne le premier cabinet par défaut (le plus courant).
        if (list.length) setCabinetId((c) => c ?? list[0].id)
        else setLoadingTree(false)
      })
      .catch(() => { if (alive) { setError('Impossible de charger la GED. Réessayez.'); setLoadingTree(false) } })
    return () => { alive = false }
  }, [])

  // ── Chargement des dossiers du cabinet courant ──
  // L'effet ne fait QUE l'appel réseau : les seuls setState synchrones du
  // changement de cabinet (reset sélection/dépliage) vivent dans le handler
  // `selectCabinet`, pas dans un effet (évite les rendus en cascade).
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
  // Sélectionner `null` vide la liste DANS le handler de sélection : l'effet ne
  // s'occupe que de l'appel réseau quand un dossier est choisi.
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

  // Sélection d'un dossier dans l'arbre : vide d'abord la liste (handler, pas
  // effet) pour éviter d'afficher les documents de l'ancien dossier.
  const selectFolder = (node) => {
    if (selected?.id !== node.id) setDocuments([])
    setSelected(node)
    if (node.hasChildren) toggle(node.id)
  }

  const tree = useMemo(() => buildFolderTree(folders), [folders])
  const visible = useMemo(() => flattenVisible(tree, expanded), [tree, expanded])
  const total = useMemo(() => countFolders(tree), [tree])

  return (
    <div className="page">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="mr-auto">
          <h1 className="text-xl font-semibold">Documents (GED)</h1>
          <p className="text-[12.5px] text-muted-foreground">
            Arborescence documentaire — dépliez un dossier pour en consulter les documents.
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
        <Button variant="secondary" onClick={() => loadFolders(cabinetId)} disabled={!cabinetId}>
          <RefreshCw className="size-4" aria-hidden="true" /> Actualiser
        </Button>
      </div>

      {error ? (
        <EmptyState title="Erreur" description={error}
          action={<Button onClick={() => loadFolders(cabinetId)}>Réessayer</Button>} />
      ) : loadingTree ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : cabinets.length === 0 ? (
        <EmptyState icon={<Folder className="size-6" aria-hidden="true" />}
          title="Aucun cabinet"
          description="Aucune armoire documentaire n'a encore été créée pour cette société." />
      ) : (
        <div className="grid gap-4 md:grid-cols-[minmax(240px,360px)_1fr]">
          {/* ── Arborescence des dossiers ── */}
          <Card>
            <CardContent className="p-2">
              <div className="mb-1 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                {total} dossier{total > 1 ? 's' : ''}
              </div>
              {visible.length === 0 ? (
                <p className="px-2 py-4 text-[13px] text-muted-foreground">
                  Aucun dossier dans ce cabinet.
                </p>
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
                          className={`flex w-full items-center gap-1.5 rounded px-1.5 py-1.5 text-left text-[13px] hover:bg-muted${isSel ? ' bg-muted font-medium' : ''}`}
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
                <EmptyState icon={<Folder className="size-6" aria-hidden="true" />}
                  title="Aucun dossier sélectionné"
                  description="Sélectionnez un dossier dans l'arborescence pour afficher ses documents." />
              ) : loadingDocs ? (
                <div className="flex items-center gap-2 p-6 text-[13px] text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Chargement des documents…
                </div>
              ) : documents.length === 0 ? (
                <EmptyState icon={<Inbox className="size-6" aria-hidden="true" />}
                  title={`Dossier « ${selected.nom} »`}
                  description="Ce dossier ne contient aucun document." />
              ) : (
                <>
                  <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
                    <FolderOpen className="size-4 text-primary" aria-hidden="true" />
                    <span className="text-[13px] font-medium">{selected.nom}</span>
                    <Badge tone="neutral" className="ml-auto">
                      {documents.length} document{documents.length > 1 ? 's' : ''}
                    </Badge>
                  </div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Document</th>
                        <th className="m-hide">Versions</th>
                        <th className="m-hide">Créé par</th>
                        <th>Mis à jour</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((d) => (
                        <tr key={d.id}>
                          <td data-label="Document" className="font-medium">
                            <span className="flex items-center gap-1.5">
                              <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                              {d.nom}
                            </span>
                          </td>
                          <td data-label="Versions" className="m-hide">
                            {d.version_count ?? 0}
                            {d.derniere_version ? ` (v${d.derniere_version})` : ''}
                          </td>
                          <td data-label="Créé par" className="m-hide">{d.created_by_nom || '—'}</td>
                          <td data-label="Mis à jour">{formatDate(d.updated_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
