import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { BookOpen, Plus, Eye, Pencil, Trash2, Send } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Button, Badge, Tag, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'
import kbApi from '../../api/kbApi'
import { KB_STATUT_MAP, StatutArticlePill, splitTags } from './kbStatus'
import ArticleDetail from './ArticleDetail'
import ArticleEditor from './ArticleEditor'
import FilterSelect from './FilterSelect'

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
  const role = useSelector((s) => s.auth?.role)
  const peutEditer = role === 'responsable' || role === 'admin'

  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFilter, setStatutFilter] = useState('')
  const [categorieFilter, setCategorieFilter] = useState('')

  // Vue courante : liste | detail | editor.
  const [selected, setSelected] = useState(null)
  const [editing, setEditing] = useState(null) // article en édition (ou {} pour nouveau)

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

  const handleRemove = async (a) => {
    if (!window.confirm(`Supprimer l'article « ${a.titre} » ?`)) return
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

  const rowActions = (a) => {
    const actions = [
      { id: 'read', label: 'Consulter', icon: Eye, onClick: () => openDetail(a) },
    ]
    if (peutEditer) {
      actions.push({ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => openEditor(a) })
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

  const actions = peutEditer ? (
    <Button onClick={() => openEditor(null)}>
      <Plus /> Nouvel article
    </Button>
  ) : null

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
      />
    </div>
  )
}
