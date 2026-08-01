import { useCallback, useState } from 'react'
import { AlertTriangle, Minus, Maximize2, Plus } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { Button, EmptyState, Skeleton } from '../../../ui'
import PlanLayer from './PlanLayer'

/* ============================================================================
   AOF92 — `CalepinageStudio` : la coquille de l'atelier de calepinage.
   ----------------------------------------------------------------------------
   Charge le calepinage CALCULÉ côté serveur (rangées explicites, tables
   posées, obstacles, zones, dégagements) et le confie à `PlanLayer`, qui le
   pose verbatim. La coquille ne possède que la FENÊTRE d'affichage (zoom,
   recadrage) — jamais une grandeur métier : les tiroirs de paramètres
   (AOF95-99), la barre de verdict (AOF93), les suggestions (AOF100) et le
   mode expert (AOF101) se greffent ensuite sur cette même coquille.

   Zoom : la molette et les trois boutons agissent sur le viewBox SVG (aucun
   re-rendu de la géométrie, aucune position recalculée) — c'est ce qui rend
   le zoom fluide sur les 314 tables du bâtiment C du dossier FRDISI.
   ========================================================================== */

const ZOOM_MIN = 0.25
const ZOOM_MAX = 12
const PAS_ZOOM = 1.25

const borne = (valeur) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, valeur))

export default function CalepinageStudio({ calepinageId }) {
  const [zoom, setZoom] = useState(1)

  const { data: calepinage, loading, error } = useResource(
    () => aoApi.calepinages.get(calepinageId),
    calepinageId,
    {
      select: (res) => res.data,
      enabled: Boolean(calepinageId),
      errorMessage: 'Impossible de charger le calepinage.',
    },
  )

  const onWheel = useCallback((event) => {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey) return
    event.preventDefault()
    setZoom((z) => borne(event.deltaY < 0 ? z * PAS_ZOOM : z / PAS_ZOOM))
  }, [])

  if (loading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[60vh] w-full" />
      </div>
    )
  }

  if (error) {
    return <EmptyState icon={AlertTriangle} title="Calepinage indisponible" description={error} />
  }

  const plan = calepinage?.plan

  if (!plan?.cadre) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Aucun plan calculé"
        description="Ce calepinage n'a pas encore de plan calculé côté serveur — lancez un calcul depuis les tiroirs de paramètres."
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Atelier de calepinage</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {calepinage?.libelle || 'Plan calculé par le moteur — affiché tel quel, aucune position recalculée.'}
          </p>
        </div>
        <div className="flex items-center gap-1" role="group" aria-label="Zoom du plan">
          <Button size="sm" variant="outline" aria-label="Dézoomer" onClick={() => setZoom((z) => borne(z / PAS_ZOOM))}>
            <Minus className="size-4" aria-hidden="true" />
          </Button>
          <Button size="sm" variant="outline" aria-label="Ajuster à la vue" onClick={() => setZoom(1)}>
            <Maximize2 className="size-4" aria-hidden="true" />
          </Button>
          <Button size="sm" variant="outline" aria-label="Zoomer" onClick={() => setZoom((z) => borne(z * PAS_ZOOM))}>
            <Plus className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col" onWheel={onWheel}>
        <PlanLayer plan={plan} zoom={zoom} titre={calepinage?.libelle || 'Plan de calepinage'} />
      </div>
    </div>
  )
}
