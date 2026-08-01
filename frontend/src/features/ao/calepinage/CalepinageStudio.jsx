import { useCallback, useState } from 'react'
import { AlertTriangle, Minus, Maximize2, Plus } from 'lucide-react'
import { Badge, Button, EmptyState, Skeleton } from '../../../ui'
import { cn } from '../../../lib/cn'
import PlanLayer from './PlanLayer'
import VerdictBar from './VerdictBar'
import TiroirKits from './TiroirKits'
import TiroirAllees from './TiroirAllees'
import TiroirRives from './TiroirRives'
import TiroirOrientation from './TiroirOrientation'
import TiroirElectrique from './TiroirElectrique'
import useCalepinage from './useCalepinage'

/* ============================================================================
   AOF92 — `CalepinageStudio` : la coquille de l'atelier de calepinage.
   ----------------------------------------------------------------------------
   Charge le calepinage CALCULÉ côté serveur (rangées explicites, tables
   posées, obstacles, zones, dégagements) et le confie à `PlanLayer`, qui le
   pose verbatim. La coquille ne possède que la FENÊTRE d'affichage (zoom,
   recadrage) — jamais une grandeur métier : les tiroirs de paramètres
   (AOF95-99), les suggestions (AOF100) et le mode expert (AOF101) se
   greffent ensuite sur cette même coquille.

   AOF93/AOF94 — la barre de verdict est permanente, et TOUT ce qui est dérivé
   (barre + plan) est estompé pendant un recalcul en vol : on n'affiche jamais
   un ancien chiffre comme s'il était courant. Les paramètres courants sont
   initialisés depuis ceux que le SERVEUR renvoie (jamais des valeurs par
   défaut inventées ici), ce qui évite un recalcul immédiat au montage.

   Zoom : la molette (avec Ctrl/⌘) et les trois boutons agissent sur le viewBox
   SVG — aucune position n'est recalculée, ce qui rend le zoom fluide sur les
   314 tables du bâtiment C du dossier FRDISI.
   ========================================================================== */

const ZOOM_MIN = 0.25
const ZOOM_MAX = 12
const PAS_ZOOM = 1.25

const borne = (valeur) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, valeur))

export default function CalepinageStudio({ calepinageId, onConformite }) {
  const [zoom, setZoom] = useState(1)
  const [parametres, setParametres] = useState(null)

  const {
    plan, resultat, parametresServeur, perime, chargementInitial, erreur,
  } = useCalepinage(calepinageId, parametres)

  // Les paramètres d'atelier viennent du serveur — jamais d'un défaut local.
  // Ajusté AU RENDU (jamais dans un effet — évite le rendu en cascade) : la
  // garde `parametres === null` fait de ce recalage une initialisation
  // ponctuelle, pas un effet qui écraserait les modifications des tiroirs.
  if (parametresServeur && parametres === null) {
    setParametres(parametresServeur)
  }

  // Un tiroir ne modifie JAMAIS un résultat : il remonte un patch de
  // paramètres, et c'est le serveur qui recalcule (AOF94).
  const majParametres = useCallback((patch) => {
    setParametres((courants) => ({ ...(courants || {}), ...patch }))
  }, [])

  const onWheel = useCallback((event) => {
    if (!event.ctrlKey && !event.metaKey) return
    event.preventDefault()
    setZoom((z) => borne(event.deltaY < 0 ? z * PAS_ZOOM : z / PAS_ZOOM))
  }, [])

  if (chargementInitial) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[60vh] w-full" />
      </div>
    )
  }

  if (erreur && !plan) {
    return <EmptyState icon={AlertTriangle} title="Calepinage indisponible" description={erreur} />
  }

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
            Plan calculé par le moteur — affiché tel quel, aucune position recalculée.
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

      <VerdictBar resultat={resultat} perime={perime} />

      {erreur && (
        <p className="text-sm text-destructive" role="alert">{erreur}</p>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <div className="relative flex min-h-0 flex-1 flex-col" onWheel={onWheel}>
          <div className={cn('flex min-h-0 flex-1 flex-col', perime && 'opacity-40')}>
            <PlanLayer plan={plan} zoom={zoom} />
          </div>
          {perime && (
            <Badge tone="neutral" className="absolute right-2 top-2">recalcul…</Badge>
          )}
        </div>

        {/* Inspecteur : tiroirs de paramètres. Chaque tiroir remonte un patch
            de paramètres ; le recalcul appartient au serveur (AOF94). */}
        <aside className="flex w-full flex-col gap-1 overflow-y-auto lg:w-96" aria-label="Tiroirs de paramètres">
          <TiroirKits
            donnees={resultat?.tiroirs?.kits}
            valeurs={parametres || {}}
            onChange={majParametres}
            perime={perime}
          />
          <TiroirAllees
            donnees={resultat?.tiroirs?.allees}
            valeurs={parametres || {}}
            onChange={majParametres}
            perime={perime}
          />
          <TiroirRives
            donnees={resultat?.tiroirs?.rives}
            valeurs={parametres || {}}
            onChange={majParametres}
          />
          <TiroirOrientation
            donnees={resultat?.tiroirs?.orientation}
            valeurs={parametres || {}}
            onChange={majParametres}
          />
          <TiroirElectrique
            donnees={resultat?.tiroirs?.electrique}
            valeurs={parametres || {}}
            onChange={majParametres}
            onConformite={onConformite}
          />
        </aside>
      </div>
    </div>
  )
}
