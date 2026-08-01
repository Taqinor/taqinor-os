// APX29 — « Ma tournée » sur la CARTE (le GPS dormait) + DÉDUPLICATION.
//
// La même tournée était rendue DEUX fois en listes numérotées quasi identiques :
// `pages/installations/PlanificationPage.jsx` (onglet « Ma tournée ») et
// `pages/interventions/MaJourneePage.jsx` (écran terrain). Elle vit désormais
// ICI, une seule fois, avec la carte en plus.
//
// Aucune donnée nouvelle : les arrêts viennent de l'endpoint « Ma tournée »
// DÉJÀ appelé par les deux écrans (`installationsApi.getMaTournee`), y compris
// `itineraire_url` (calculé par l'endpoint, ce n'est pas un champ de modèle) et
// le GPS du chantier (`gps_lat`/`gps_lng`, servis par le sérialiseur). Zéro
// endpoint nouveau, zéro clé, zéro service de routage.
import { lazy, Suspense, useMemo } from 'react'
import { ExternalLink, MapPin, Navigation } from 'lucide-react'
import { Spinner } from '../../ui'

// La carte (Leaflet) est un gros module : chargée à la demande, comme sur les
// deux autres écrans qui l'utilisent.
const MapView = lazy(() => import('../../components/MapView'))

// Un arrêt géolocalisable ? (le GPS du chantier est nullable côté serveur)
const aGps = (s) => s?.gps_lat != null && s?.gps_lng != null

// Helper PUR co-localise avec le composant qui l'utilise ; l'extraire casserait
// les tests sonde qui epinglent le texte source de CE fichier. Regle HMR de dev.
// eslint-disable-next-line react-refresh/only-export-components
export const stopLabel = (stop, rang) => (
  `${rang}. ${stop?.client_nom || stop?.installation_reference || `#${stop?.id}`}`
)

// Marqueurs numérotés DANS L'ORDRE de la tournée (l'ordre serveur, plus proche
// voisin) — les arrêts sans GPS sont simplement absents de la carte, jamais
// posés à une position inventée ; ils restent visibles dans la liste.
// Helper PUR co-localise avec le composant qui l'utilise ; l'extraire casserait
// les tests sonde qui epinglent le texte source de CE fichier. Regle HMR de dev.
// eslint-disable-next-line react-refresh/only-export-components
export function tourneeMarkers(stops) {
  return (stops ?? []).map((stop, i) => ({ stop, rang: i + 1 }))
    .filter(({ stop }) => aGps(stop))
    .map(({ stop, rang }) => ({
      id: stop.id,
      lat: Number(stop.gps_lat),
      lng: Number(stop.gps_lng),
      badge: rang,
      label: stopLabel(stop, rang),
      color: '#2563eb',
    }))
}

// Helper PUR co-localise avec le composant qui l'utilise ; l'extraire casserait
// les tests sonde qui epinglent le texte source de CE fichier. Regle HMR de dev.
// eslint-disable-next-line react-refresh/only-export-components
export const tourneePath = (stops) => tourneeMarkers(stops).map((m) => [m.lat, m.lng])

/**
 * Carte (+ liste) des arrêts d'une tournée.
 * Desktop : carte à gauche, liste à droite. Mobile : carte au-dessus, liste
 * dessous (même composant, une seule grille responsive).
 *
 * `showList={false}` : la CARTE seule. « Ma journée » garde ses cartes terrain
 * riches (statut, priorité, photos manquantes, météo, appeler/naviguer —
 * VX42/VX226) : ce qui était dupliqué entre les deux écrans et qui vit
 * désormais ICI, c'est la carte, la numérotation des arrêts et le lien
 * « Itinéraire » de l'endpoint.
 */
export default function TourneeStops({
  stops = [], mapHeight = '340px', onStopClick, showList = true,
}) {
  // Mémoïsés : MapView redessine ses couches à chaque changement d'identité de
  // `markers`/`path` (effet Leaflet impératif).
  const markers = useMemo(() => tourneeMarkers(stops), [stops])
  const path = useMemo(() => tourneePath(stops), [stops])

  return (
    <div
      className={showList
        ? 'grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]'
        : 'grid gap-3'}
      data-testid="tournee-stops">
      <div className="order-1 min-w-0">
        {markers.length === 0 ? (
          <p className="flex items-center gap-2 rounded-lg border border-dashed border-border p-3 text-sm text-muted-foreground"
            data-testid="tournee-sans-gps">
            <MapPin className="size-4" aria-hidden="true" />
            Aucun arrêt géolocalisé — la carte s’affichera dès qu’un chantier
            portera ses coordonnées GPS.
          </p>
        ) : (
          <Suspense fallback={(
            <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Spinner className="size-4" /> Chargement de la carte…
            </p>
          )}>
            <MapView markers={markers} path={path} height={mapHeight}
              onMarkerClick={onStopClick ? (m) => {
                const stop = stops.find((s) => String(s.id) === String(m.id))
                if (stop) onStopClick(stop)
              } : undefined} />
          </Suspense>
        )}
      </div>

      {showList && (
      <ol className="order-2 flex flex-col gap-2" data-testid="tournee-liste">
        {stops.map((stop, i) => (
          <li key={stop.id}>
            <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">
                  {stop.client_nom ?? stop.installation_reference ?? `#${stop.id}`}
                </div>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  {stop.site_ville ?? '—'}
                  {!aGps(stop) && <span>· sans GPS</span>}
                </div>
              </div>
              {stop.itineraire_url && (
                <a href={stop.itineraire_url} target="_blank" rel="noreferrer"
                  className="flex min-h-11 shrink-0 items-center gap-1 px-2 text-xs font-medium text-primary hover:underline"
                  aria-label={`Itinéraire vers ${stop.client_nom ?? stop.installation_reference ?? `l'arrêt ${i + 1}`}`}>
                  <Navigation className="size-3.5" aria-hidden="true" />
                  Itinéraire
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                </a>
              )}
            </div>
          </li>
        ))}
      </ol>
      )}
    </div>
  )
}
