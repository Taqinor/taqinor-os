import { useEffect, useState } from 'react'
import { Filter, RotateCcw } from 'lucide-react'
import { Button, Label, toast } from '../../ui'
import coreApi from '../../api/coreApi'
import {
  DEFAULT_GLOBAL_FILTERS, readGlobalFilters, writeGlobalFilters,
  effectiveParamsForAllWidgets, hasActiveFilters,
} from './dashboardFilters'

/* XPLT9 — Barre de filtres globaux d'un dashboard FG381 (plage de dates,
   commercial, canal, catégorie produit), mémorisée dans
   `Dashboard.layout.globalFilters` (clé JSON additive, aucune migration).
   Changer un filtre recharge TOUS les widgets d'un coup via `onReload`
   (fourni par le futur écran de rendu des widgets — ce composant ne connaît
   pas leur affichage, seulement le calcul des paramètres effectifs par
   widget, cf. `dashboardFilters.effectiveParamsForAllWidgets`).

   BLOQUÉ (constaté, pas construit ici) : aucun écran constructeur/rendu de
   widgets FG381 n'existe encore côté frontend (`core.Dashboard` n'a qu'un
   CRUD REST backend, `/api/django/core/dashboards/`) — ce composant est prêt
   à être monté au-dessus de ce futur écran dès qu'il existe ; en attendant,
   il fonctionne de façon autonome sur un `dashboardId` donné (lecture/
   écriture réelles du layout via `coreApi.dashboards`), guardé contre un
   dashboard introuvable/layout vide (jamais un crash). */
export default function DashboardFilterBar({ dashboardId, layout, onLayoutChange, onReload }) {
  const [filters, setFilters] = useState(() => readGlobalFilters(layout))
  const [saving, setSaving] = useState(false)

  // Un changement de dashboard (id différent) recharge les filtres mémorisés
  // pour CE dashboard — jamais ceux du précédent.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resynchronise les filtres affichés à chaque changement de dashboardId (source externe, pas un dérivé de rendu)
    setFilters(readGlobalFilters(layout))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboardId])

  const persist = async (next) => {
    setFilters(next)
    const nextLayout = writeGlobalFilters(layout, next)
    onLayoutChange?.(nextLayout)
    onReload?.(effectiveParamsForAllWidgets(nextLayout, next))
    if (!dashboardId) return // dashboard pas encore enregistré : pas d'appel réseau
    setSaving(true)
    try {
      await coreApi.dashboards.updateLayout(dashboardId, nextLayout)
    } catch {
      toast.error('Le filtre n’a pas pu être enregistré (resterá actif pour cette session).')
    } finally {
      setSaving(false)
    }
  }

  const set = (key) => (e) => {
    const value = e?.target ? e.target.value : e
    persist({ ...filters, [key]: value })
  }

  const reset = () => persist({ ...DEFAULT_GLOBAL_FILTERS })

  return (
    <form
      noValidate
      onSubmit={(e) => e.preventDefault()}
      className="flex flex-wrap items-end gap-3 rounded-md border border-border bg-card p-3"
      data-testid="dashboard-filter-bar"
    >
      <Filter className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />

      <div className="flex flex-col gap-1">
        <Label htmlFor="df-from">Du</Label>
        <input
          id="df-from" type="date" step="any"
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
          value={filters.dateFrom} onChange={set('dateFrom')}
        />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="df-to">Au</Label>
        <input
          id="df-to" type="date" step="any"
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
          value={filters.dateTo} onChange={set('dateTo')}
        />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="df-commercial">Commercial</Label>
        <input
          id="df-commercial" type="text"
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
          value={filters.commercial} onChange={set('commercial')}
        />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="df-canal">Canal</Label>
        <input
          id="df-canal" type="text"
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
          value={filters.canal} onChange={set('canal')}
        />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="df-categorie">Catégorie produit</Label>
        <input
          id="df-categorie" type="text"
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
          value={filters.categorieProduit} onChange={set('categorieProduit')}
        />
      </div>

      <Button
        type="button" variant="ghost" size="sm"
        disabled={!hasActiveFilters(filters) || saving}
        onClick={reset}
      >
        <RotateCcw className="size-4" aria-hidden="true" /> Réinitialiser
      </Button>
    </form>
  )
}
