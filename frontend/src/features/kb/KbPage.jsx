import { useEffect, useMemo, useRef, useState } from 'react'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import {
  BookOpen, Plus, Eye, Pencil, Trash2, Send, FolderTree, Copy, AlertTriangle,
  LayoutTemplate, Download, Upload, Star, BarChart3,
} from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Button, Badge, Tag, toast, buttonVariants } from '../../ui'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { formatDateTime } from '../../lib/format'
import kbApi from '../../api/kbApi'
import { KB_STATUT_MAP, StatutArticlePill, splitTags } from './kbStatus'
import ArticleDetail from './ArticleDetail'
import ArticleEditor from './ArticleEditor'
import FilterSelect from './FilterSelect'
import ArticleTree from './ArticleTree'
import TemplatesGallery from './TemplatesGallery'
import KbStatsPanel from './KbStatsPanel'
import FavorisRecentsPanel from './FavorisRecentsPanel'

/* ============================================================================
   UX43 — Base de connaissances (apps/kb).
   ----------------------------------------------------------------------------
   Navigateur d'articles (catégories/tags, recherche + filtres via ListShell),
   lecture pour TOUS les rôles, édition/publication réservée responsable/admin.
   Ouvre un détail (versions, marquer-lu, ACL) ou l'éditeur (brouillon→publié).
   Données via useState/useEffect + kbApi ; aucun react-query.
   ========================================================================== */

const STATUT_FILTER_OPTIONS = [
  { value: '', label: 'Tous les statuts' },
  ...Object.entries(KB_STATUT_MAP).map(([value, v]) => ({ value, label: v.label })),
]

export default function KbPage() {
  const peutEditer = useIsAdminOrResponsable()

  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('')
  const [categorieFilter, setCategorieFilter] = useState('')

  // Vue courante : liste | detail | editor.
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(null) // article en édition (ou {} pour nouveau)

  // XKB14 — rapport de péremption (articles dont la revue est due), visible
  // seulement responsable/admin.
  const [peremption, setPeremption] = useState([])

  // XKB12 — galerie de gabarits (masquée par défaut).
  const [showGabarits, setShowGabarits] = useState(false)
  // XKB16 — statistiques (masquées par défaut, responsable/admin).
  const [showStats, setShowStats] = useState(false)
  // XKB15 — favoris/récents (masqués par défaut, tous rôles).
  const [showFavoris, setShowFavoris] = useState(false)
  // XKB17 — import Markdown (input fichier caché, déclenché par le bouton).
  const importInputRef = useRef(null)

  // Charge la liste avec les filtres serveur passés (statut / catégorie).
  const load = (statut = statutFilter, categorie = categorieFilter) => {
    setLoading(true)
    setError(null)
    const params = {}
    if (statut) params.statut = statut
    if (categorie) params.categorie = categorie
    kbApi.listArticles(params)
      .then((res) => setArticles(
        Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les articles.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!peutEditer) return
    kbApi.rapportPeremption()
      .then((res) => setPeremption(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setPeremption([]))
  }, [peutEditer])

  // Les filtres serveur relancent explicitement le chargement (évite un effet
  // dépendant qui déclencherait un setState « en cascade »).
  const onStatut = (v) => { setStatutFilter(v); load(v, categorieFilter) }
  const onCategorie = (v) => { setCategorieFilter(v); load(statutFilter, v) }

  // Catégories connues (dérivées des articles chargés) pour le filtre.
  const categories = useMemo(() => {
    const set = new Set()
    for (const a of articles) if (a.categorie) set.add(a.categorie)
    return Array.from(set).sort()
  }, [articles])

  const openDetail = (a) => setSelected(a)
  const openEditor = (a) => setEditing(a ?? {})
  const closeAll = () => { setSelected(null); setEditing(null) }

  // VX241(a) — le confirm() générique mentait par omission : supprimer un
  // article-PARENT (`parent` est on_delete=CASCADE) détruit tout le
  // sous-arbre sans le dire. Affiche désormais le compte RÉEL de
  // descendants (backend, jamais recalculé client-side sur une liste
  // potentiellement filtrée/paginée) avant toute confirmation.
  const [confirmRemove, setConfirmRemove] = useState(null) // { article, nbDescendants, loading } | null

  const handleRemove = (a) => {
    setConfirmRemove({ article: a, nbDescendants: null, loading: true })
    kbApi.descendantsCount(a.id)
      .then(({ data }) => setConfirmRemove(
        (s) => (s && s.article.id === a.id
          ? { ...s, nbDescendants: data?.nb_descendants ?? 0, loading: false }
          : s)))
      .catch(() => setConfirmRemove(
        (s) => (s && s.article.id === a.id ? { ...s, loading: false } : s)))
  }

  const confirmRemoveArticle = async () => {
    if (!confirmRemove) return
    const a = confirmRemove.article
    setConfirmRemove(null)
    try {
      await kbApi.removeArticle(a.id)
      toast.success('Article supprimé.')
      closeAll()
      load()
    } catch {
      toast.error('Suppression impossible.')
    }
  }

  const columns = useMemo(() => [
    {
      id: 'titre',
      header: 'Titre',
      width: 260,
      accessor: (a) => a.titre,
      cell: (value) => <span className="font-medium">{value || '—'}</span>,
    },
    {
      id: 'categorie',
      header: 'Catégorie',
      width: 150,
      accessor: (a) => a.categorie || '',
      cell: (value) => (value
        ? <Badge tone="info">{value}</Badge>
        : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'tags',
      header: 'Tags',
      width: 200,
      accessor: (a) => a.tags || '',
      cell: (value) => {
        const tags = splitTags(value)
        if (!tags.length) return <span className="text-muted-foreground">—</span>
        return (
          <span className="flex flex-wrap gap-1">
            {tags.slice(0, 4).map((t) => <Tag key={t}>{t}</Tag>)}
          </span>
        )
      },
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      accessor: (a) => a.statut,
      cell: (value) => <StatutArticlePill status={value} />,
    },
    {
      id: 'auteur',
      header: 'Auteur',
      width: 150,
      accessor: (a) => a.auteur_nom || '',
      cell: (value) => value || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'date_modification',
      header: 'Modifié',
      width: 150,
      align: 'right',
      searchable: false,
      accessor: (a) => a.date_modification || '',
      cell: (value) => (
        <span className="text-muted-foreground">
          {value ? formatDateTime(value) : '—'}
        </span>
      ),
    },
  ], [])

  // XKB21 — duplique l'article (copie brouillon indépendante).
  const handleDuplicate = async (a) => {
    const avecSousArticles = window.confirm(
      `Dupliquer « ${a.titre} » ? OK = avec ses sous-articles, Annuler = article seul.`)
    try {
      await kbApi.dupliquer(a.id, { avec_sous_articles: avecSousArticles })
      toast.success('Article dupliqué (brouillon).')
      load()
    } catch { toast.error('Duplication impossible.') }
  }

  // XKB8 — déplace (re-parente) l'article : demande l'id du nouveau parent
  // (vide = racine). Interaction volontairement simple (prompt) — le
  // panneau ArticleTree reste la vue de référence pour visualiser l'arbre.
  const handleMove = async (a) => {
    const input = window.prompt(
      `Déplacer « ${a.titre} » — identifiant de l’article parent (laisser vide pour la racine) :`,
      a.parent ?? '')
    if (input === null) return
    const parent = input.trim() === '' ? null : Number(input.trim())
    if (parent !== null && Number.isNaN(parent)) {
      toast.error('Identifiant de parent invalide.')
      return
    }
    try {
      await kbApi.deplacer(a.id, { parent })
      toast.success('Article déplacé.')
      load()
    } catch { toast.error('Déplacement impossible.') }
  }

  const rowActions = (a) => {
    const actions = [
      { id: 'read', label: 'Consulter', icon: Eye, onClick: () => openDetail(a) },
    ]
    if (peutEditer) {
      actions.push({ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => openEditor(a) })
      actions.push({ id: 'move', label: 'Déplacer', icon: FolderTree, onClick: () => handleMove(a) })
      actions.push({ id: 'duplicate', label: 'Dupliquer', icon: Copy, onClick: () => handleDuplicate(a) })
      if (a.statut !== 'publie') {
        actions.push({
          id: 'publish', label: 'Publier', icon: Send,
          onClick: async () => {
            try {
              await kbApi.publier(a.id)
              toast.success('Article publié.')
              load()
            } catch { toast.error('Publication impossible.') }
          },
        })
      }
      actions.push({
        id: 'delete', label: 'Supprimer', icon: Trash2,
        destructive: true, separatorBefore: true,
        onClick: () => handleRemove(a),
      })
    }
    return actions
  }

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
      <FilterSelect
        value={statutFilter}
        onChange={onStatut}
        options={STATUT_FILTER_OPTIONS}
        aria-label="Filtrer par statut"
      />
      <FilterSelect
        value={categorieFilter}
        onChange={onCategorie}
        options={[
          { value: '', label: 'Toutes les catégories' },
          ...categories.map((c) => ({ value: c, label: c })),
        ]}
        aria-label="Filtrer par catégorie"
      />
    </div>
  )

  // XKB17 — import Markdown : crée un nouvel article BROUILLON depuis un
  // fichier .md sélectionné.
  const handleImportMarkdown = async (e) => {
    const fichier = e.target.files?.[0]
    e.target.value = ''
    if (!fichier) return
    try {
      await kbApi.importerMarkdown({ fichier })
      toast.success('Article importé (brouillon).')
      load()
    } catch { toast.error('Import impossible.') }
  }

  const actions = (
    <>
      <Button variant="outline" onClick={() => setShowFavoris(true)}>
        <Star /> Favoris &amp; récents
      </Button>
      {peutEditer && (
        <>
          <Button variant="outline" onClick={() => setShowStats(true)}>
            <BarChart3 /> Statistiques
          </Button>
          <Button variant="outline" onClick={() => setShowGabarits(true)}>
            <LayoutTemplate /> Gabarits
          </Button>
          {/* Lien de téléchargement stylé comme un bouton — pas de Button
              asChild (Slot Radix exige un unique enfant, incompatible avec
              icône + libellé ici). */}
          <a href={kbApi.exportZipUrl()} download className={buttonVariants({ variant: 'outline' })}>
            <Download /> Exporter (ZIP)
          </a>
          <Button variant="outline" onClick={() => importInputRef.current?.click()}>
            <Upload /> Importer Markdown
          </Button>
          <input
            ref={importInputRef}
            type="file"
            accept=".md,text/markdown,text/plain"
            className="hidden"
            onChange={handleImportMarkdown}
          />
          <Button onClick={() => openEditor(null)}>
            <Plus /> Nouvel article
          </Button>
        </>
      )}
    </>
  )

  // ── Galerie de gabarits (XKB12) ──
  if (showGabarits) {
    return (
      <div className="page">
        <TemplatesGallery
          onClose={() => setShowGabarits(false)}
          onCreated={(article) => { setShowGabarits(false); openEditor(article) }}
        />
      </div>
    )
  }

  // ── Statistiques (XKB16) ──
  if (showStats) {
    return (
      <div className="page">
        <KbStatsPanel onClose={() => setShowStats(false)} />
      </div>
    )
  }

  // ── Favoris & récents (XKB15) ──
  if (showFavoris) {
    return (
      <div className="page">
        <FavorisRecentsPanel
          onClose={() => setShowFavoris(false)}
          onSelect={(a) => { setShowFavoris(false); openDetail(a) }}
        />
      </div>
    )
  }

  // ── Éditeur (création / édition) ──
  if (editing) {
    return (
      <ArticleEditor
        article={editing.id ? editing : null}
        onCancel={closeAll}
        onSaved={() => { closeAll(); load() }}
      />
    )
  }

  // ── Détail (lecture + versions + marquer-lu + ACL) ──
  if (selected) {
    return (
      <ArticleDetail
        articleId={selected.id}
        canEdit={peutEditer}
        onBack={closeAll}
        onEdit={() => openEditor(selected)}
        onChanged={load}
        onOpenArticle={(id) => openDetail({ id })}
      />
    )
  }

  // ── Liste ──
  return (
    <div className="page">
      <ListShell
        title="Base de connaissances"
        subtitle={
          <span className="inline-flex items-center gap-1.5">
            <BookOpen className="size-4" aria-hidden="true" />
            Procédures, fiches techniques et FAQ internes
          </span>
        }
        actions={actions}
        filters={filters}
        columns={columns}
        rows={articles}
        loading={loading}
        error={error}
        onRowClick={openDetail}
        rowActions={rowActions}
        searchable
        searchPlaceholder="Rechercher un article…"
        exportName="base-de-connaissances"
        emptyTitle="Aucun article"
        emptyDescription="Aucun article ne correspond à cette recherche."
      >
        {peutEditer && peremption.length > 0 && (
          <div className="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            {peremption.length} article{peremption.length > 1 ? 's' : ''} dont la revue
            est due (contenu potentiellement périmé).
          </div>
        )}
        <ArticleTree onSelect={openDetail} />
      </ListShell>

      {confirmRemove && (
        // VX244 — KB-avec-enfants : dialog PONDÉRÉ. Un article SANS
        // sous-arbre reste `medium` (pas de saisie) ; un article-PARENT
        // (nbDescendants > 0 — toute la branche part avec lui, CASCADE)
        // passe en `high` : confirmation TAPÉE du titre exact.
        <ConfirmDialog
          open
          onOpenChange={(o) => { if (!o) setConfirmRemove(null) }}
          severity={confirmRemove.nbDescendants > 0 ? 'high' : 'medium'}
          title="Supprimer cet article ?"
          description={
            `« ${confirmRemove.article.titre} » sera supprimé définitivement.`
            + (confirmRemove.loading
              ? ' Calcul des sous-articles…'
              : confirmRemove.nbDescendants > 0
                ? ` Ceci supprimera AUSSI ${confirmRemove.nbDescendants} `
                  + `sous-article${confirmRemove.nbDescendants > 1 ? 's' : ''} (toute la branche).`
                : " Cet article n'a aucun sous-article.")
          }
          confirmText={confirmRemove.nbDescendants > 0 ? confirmRemove.article.titre : undefined}
          confirmLabel="Supprimer"
          loading={confirmRemove.loading}
          onConfirm={confirmRemoveArticle}
        />
      )}
    </div>
  )
}
