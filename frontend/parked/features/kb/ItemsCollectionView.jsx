import { useEffect, useState } from 'react'
import { LayoutGrid, List, Kanban, Calendar } from 'lucide-react'
import { Badge, EmptyState, Spinner } from '../../ui'
import kbApi from '../../api/kbApi'
import customFieldsApi from '../../api/customFieldsApi'
import FilterSelect from './FilterSelect'

/* ============================================================================
   ZGED11 — Sous-articles rendus comme une COLLECTION structurée (liste /
   cartes / kanban / calendrier), à partir du même sélecteur backend
   (``kbApi.items``) qui résout les propriétés effectives (héritées du
   parent). Kanban/calendrier regroupent par une propriété choisie.
   ========================================================================== */

const VUE_OPTIONS = [
  { value: 'liste', label: 'Liste', icon: List },
  { value: 'cartes', label: 'Cartes', icon: LayoutGrid },
  { value: 'kanban', label: 'Kanban', icon: Kanban },
  { value: 'calendrier', label: 'Calendrier', icon: Calendar },
]

function ItemCard({ item, onSelect }) {
  const proprietes = Object.entries(item.proprietes || {})
  return (
    <button
      type="button"
      onClick={() => onSelect?.(item)}
      className="flex w-full flex-col gap-1.5 rounded-lg border border-border p-3 text-left hover:bg-muted/60"
    >
      <span className="font-medium">{item.titre}</span>
      {proprietes.length > 0 && (
        <span className="flex flex-wrap gap-1">
          {proprietes.map(([k, v]) => (
            <Badge key={k} tone="neutral">{k}: {String(v)}</Badge>
          ))}
        </span>
      )}
    </button>
  )
}

export default function ItemsCollectionView({ articleId, onSelect }) {
  const [vue, setVue] = useState('liste')
  const [propriete, setPropriete] = useState('')
  const [proprieteDefs, setProprieteDefs] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    customFieldsApi.getDefs('kb_article')
      .then((res) => setProprieteDefs(
        (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
          .filter((d) => d.actif)))
      .catch(() => setProprieteDefs([]))
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-vue-change
    setLoading(true)
    const params = { vue }
    if (propriete) params.propriete = propriete
    kbApi.items(articleId, params)
      .then((res) => setData(res.data))
      .catch(() => setData(vue === 'liste' || vue === 'cartes' ? [] : {}))
      .finally(() => setLoading(false))
  }, [articleId, vue, propriete])

  const isGroupedView = vue === 'kanban' || vue === 'calendrier'
  const items = Array.isArray(data) ? data : []
  const groupes = isGroupedView && data && !Array.isArray(data) ? data : null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <FilterSelect
          value={vue}
          onChange={setVue}
          aria-label="Type de vue"
          options={VUE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
        />
        {isGroupedView && (
          <FilterSelect
            value={propriete}
            onChange={setPropriete}
            aria-label="Propriété de regroupement"
            options={[
              { value: '', label: 'Choisir une propriété…' },
              ...proprieteDefs.map((d) => ({ value: d.code, label: d.libelle })),
            ]}
          />
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement…
        </div>
      )}

      {!loading && !isGroupedView && (
        items.length ? (
          <div className={vue === 'cartes' ? 'grid gap-2 sm:grid-cols-2 lg:grid-cols-3' : 'flex flex-col gap-1.5'}>
            {items.map((it) => <ItemCard key={it.id} item={it} onSelect={onSelect} />)}
          </div>
        ) : (
          <EmptyState title="Aucun sous-article" description="Cet article n’a pas encore de sous-articles." />
        )
      )}

      {!loading && isGroupedView && groupes && Object.keys(groupes).length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(groupes).map(([cle, groupItems]) => (
            <div key={cle} className="flex flex-col gap-2 rounded-lg border border-border p-3">
              <h4 className="text-sm font-medium">
                {cle === '__aucune__' ? 'Sans valeur' : cle}
              </h4>
              <div className="flex flex-col gap-1.5">
                {groupItems.map((it) => <ItemCard key={it.id} item={it} onSelect={onSelect} />)}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && isGroupedView && (!groupes || Object.keys(groupes).length === 0) && (
        <EmptyState
          title="Aucune donnée"
          description={propriete
            ? 'Aucun sous-article ne porte cette propriété.'
            : 'Choisissez une propriété pour regrouper les sous-articles.'}
        />
      )}
    </div>
  )
}
