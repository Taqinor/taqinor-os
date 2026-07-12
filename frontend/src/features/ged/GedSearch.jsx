// GED13 — Filtres & recherche avancée (frontend). Barre de recherche
// plein-texte (GED11, endpoint /recherche) avec bascule recherche sémantique
// (GED12, dégrade en plein-texte sans clé), plus un filtre par tag de la
// taxonomie (GED9). La logique pure (params, normalisation, filtrage client)
// vit dans `search.js` (testée). Affiche les résultats dans une table FR.
import { useEffect, useMemo, useState } from 'react'
import { Search, FileText, Tag as TagIcon, Loader2, Inbox, X } from 'lucide-react'
import gedApi from '../../api/gedApi'
import { formatDate } from '../../lib/format'
import {
  Card, CardContent, Button, EmptyState, Badge, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { DataTable } from '../../ui/datatable'
import {
  rows, normalizeQuery, hasActiveSearch, filterDocuments,
} from './search.js'

// VX152 — les résultats de recherche rejoignent le moteur DataTable partagé
// (fin de la table HTML héritée). Liste seule : résultats pré-filtrés/triés
// côté serveur (seams manuels), aucune barre d'outils.
const GED_SEARCH_COLUMNS = [
  {
    id: 'nom', header: 'Document', sortable: false, hideable: false, reorderable: false,
    accessor: (d) => d.nom,
    cell: (v) => (
      <span className="flex items-center gap-1.5 font-medium">
        <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        {v}
      </span>
    ),
  },
  {
    id: 'tags', header: 'Tags', sortable: false, hideable: false, reorderable: false,
    accessor: (d) => (d.tags || []).map((t) => t.nom).join(' '),
    cell: (unused, d) => ((d.tags || []).length === 0 ? '—' : (
      <span className="flex flex-wrap gap-1">
        {(d.tags || []).map((t) => (
          <Badge key={t.id} tone="neutral">
            <TagIcon className="size-3" aria-hidden="true" /> {t.nom}
          </Badge>
        ))}
      </span>
    )),
  },
  {
    id: 'folder', header: 'Dossier', sortable: false, hideable: false, reorderable: false,
    accessor: (d) => d.folder_nom || '—',
  },
  {
    id: 'updated', header: 'Mis à jour', sortable: false, hideable: false, reorderable: false,
    accessor: (d) => formatDate(d.updated_at),
  },
]

export default function GedSearch() {
  const [query, setQuery] = useState('')
  const [semantic, setSemantic] = useState(false)
  const [tagId, setTagId] = useState('')
  const [tags, setTags] = useState([])
  const [results, setResults] = useState([])
  const [mode, setMode] = useState(null) // 'plein-texte' | 'semantique' | null
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [searched, setSearched] = useState(false)

  // Charge la taxonomie de tags (filtre par tag).
  useEffect(() => {
    let alive = true
    gedApi.getTags()
      .then((r) => { if (alive) setTags(rows(r)) })
      .catch(() => { if (alive) setTags([]) })
    return () => { alive = false }
  }, [])

  const active = useMemo(
    () => hasActiveSearch({ query, tag: tagId }), [query, tagId])

  const runSearch = (e) => {
    e?.preventDefault?.()
    const q = normalizeQuery(query)
    if (!active) return
    setLoading(true)
    setError(null)
    setSearched(true)
    // Recherche serveur (plein-texte ou sémantique) si une requête texte
    // existe ; sinon, on liste par tag seul.
    const call = q
      ? (semantic
        ? gedApi.semanticSearch({ q })
        : gedApi.searchDocuments({ q }))
      : gedApi.getDocuments({ tag: tagId })
    call
      .then((r) => {
        setMode(q ? (r?.data?.mode || (semantic ? 'semantique' : 'plein-texte')) : null)
        // Filtre client complémentaire par tag (par-dessus le résultat texte).
        const list = rows(r)
        const filtered = tagId
          ? filterDocuments(list, { tagIds: [tagId] })
          : list
        setResults(filtered)
      })
      .catch(() => { setError('La recherche a échoué. Réessayez.'); setResults([]) })
      .finally(() => setLoading(false))
  }

  const reset = () => {
    setQuery(''); setTagId(''); setSemantic(false)
    setResults([]); setSearched(false); setMode(null); setError(null)
  }

  return (
    <Card>
      <CardContent className="p-3">
        <form onSubmit={runSearch} className="flex flex-wrap items-end gap-2">
          <div className="min-w-[200px] flex-1">
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Recherche plein-texte
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="Nom, description, texte OCR…" className="pl-8"
                aria-label="Recherche plein-texte" />
            </div>
          </div>
          <div className="w-[180px]">
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Tag
            </label>
            <Select value={tagId ? String(tagId) : ''}
              onValueChange={(v) => setTagId(v === '__all__' ? '' : Number(v))}>
              <SelectTrigger aria-label="Filtrer par tag">
                <SelectValue placeholder="Tous les tags" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Tous les tags</SelectItem>
                {tags.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.chemin || t.nom}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-1.5 pb-2 text-sm">
            <input type="checkbox" checked={semantic}
              onChange={(e) => setSemantic(e.target.checked)} />
            Sémantique
          </label>
          <Button type="submit" disabled={!active || loading}>
            <Search className="size-4" aria-hidden="true" /> Rechercher
          </Button>
          {searched && (
            <Button type="button" variant="ghost" onClick={reset}>
              <X className="size-4" aria-hidden="true" /> Effacer
            </Button>
          )}
        </form>

        {error ? (
          <p className="mt-3 text-sm text-destructive">{error}</p>
        ) : loading ? (
          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Recherche en cours…
          </div>
        ) : searched ? (
          results.length === 0 ? (
            <EmptyState icon={Inbox}
              title="Aucun résultat"
              description="Aucun document ne correspond à ces critères." />
          ) : (
            <div className="mt-3">
              <div className="mb-2 flex items-center gap-2">
                <Badge tone="neutral">
                  {results.length} résultat{results.length > 1 ? 's' : ''}
                </Badge>
                {mode === 'semantique' && (
                  <Badge tone="info">Recherche sémantique</Badge>
                )}
                {mode === 'plein-texte' && semantic && (
                  <Badge tone="neutral">Plein-texte (sémantique indisponible)</Badge>
                )}
              </div>
              <DataTable
                data={results}
                columns={GED_SEARCH_COLUMNS}
                getRowId={(d) => d.id}
                manualSorting
                manualFiltering
                manualPagination
                rowCount={results.length}
                pageSize={results.length}
                pageSizeOptions={[results.length]}
                searchable={false}
                hideToolbar
                hidePagination
                tableRole="table"
                aria-label="Résultats de recherche"
              />
            </div>
          )
        ) : null}
      </CardContent>
    </Card>
  )
}
