/**
 * RoofViewer — QG11 : rendu LECTURE SEULE du tracé de toiture stocké sur un
 * devis (`roof_layout` sérialisé par l'outil roofPro11, cf.
 * apps/web/src/scripts/roofPro11/prefill.ts → serializeLayout).
 *
 * Ce composant N'ÉDITE RIEN : pas de carte MapTiler, pas de bouton, pas d'appel
 * réseau. Il projette les sommets lng/lat des zones dans un petit SVG (mise à
 * l'échelle sur la boîte englobante), dessine chaque polygone de zone + ses
 * obstacles (zones d'exclusion), et affiche un résumé (nombre de zones,
 * panneaux, type de toit, inclinaison, orientation). Il ne dépend PAS du builder
 * 3D — aucune régression possible sur l'édition (ToitureDesign.jsx reste seul à
 * booter l'outil complet).
 *
 * Dégradation propre : sans `layout` (ou sans aucune zone géométrique), un état
 * vide explicite est rendu — jamais de plantage, jamais de SVG dégénéré.
 *
 * Props :
 *   - layout : l'objet `roof_layout` du devis (peut être null/undefined).
 *   - imageUrl : URL éventuelle d'un aperçu image (snapshot 3D) — optionnel ;
 *                si présent, affiché en priorité au-dessus du plan SVG.
 *   - className : classes conteneur additionnelles.
 */

// Azimut (degrés) → libellé cardinal français court.
function azimuthLabel(deg) {
  if (deg == null || Number.isNaN(Number(deg))) return null
  const d = ((Number(deg) % 360) + 360) % 360
  const dirs = [
    [0, 'Nord'], [45, 'Nord-Est'], [90, 'Est'], [135, 'Sud-Est'],
    [180, 'Sud'], [225, 'Sud-Ouest'], [270, 'Ouest'], [315, 'Nord-Ouest'],
  ]
  let best = dirs[0]
  let bestDiff = 360
  for (const [a, label] of dirs) {
    const diff = Math.min(Math.abs(d - a), 360 - Math.abs(d - a))
    if (diff < bestDiff) { bestDiff = diff; best = [a, label] }
  }
  return `${best[1]} · ${Math.round(d)}°`
}

const ROOF_TYPE_LABEL = { flat: 'Toit plat', pitched: 'Toit en pente / tuiles' }

// Convertit les mètres d'un obstacle (largeur/longueur) en degrés approximatifs
// pour le dessiner à l'échelle de la projection (approximation locale suffisante
// pour un aperçu — jamais un calcul métier). ~111 320 m par degré de latitude.
const M_PER_DEG_LAT = 111320

/**
 * Extrait la géométrie affichable : liste des zones avec sommets [lng,lat],
 * obstacles, et la boîte englobante globale. Retourne null si rien à dessiner.
 * Interne au module (non exporté pour préserver le fast-refresh du composant).
 */
function extractGeometry(layout) {
  if (!layout || typeof layout !== 'object') return null
  const zones = Array.isArray(layout.zones) ? layout.zones : []
  const drawable = []
  let minLng = Infinity; let maxLng = -Infinity
  let minLat = Infinity; let maxLat = -Infinity

  for (const z of zones) {
    const verts = Array.isArray(z?.vertices) ? z.vertices : []
    const pts = verts
      .filter(v => Array.isArray(v) && v.length >= 2
        && Number.isFinite(Number(v[0])) && Number.isFinite(Number(v[1])))
      .map(v => [Number(v[0]), Number(v[1])])
    if (pts.length < 3) continue
    for (const [lng, lat] of pts) {
      if (lng < minLng) minLng = lng
      if (lng > maxLng) maxLng = lng
      if (lat < minLat) minLat = lat
      if (lat > maxLat) maxLat = lat
    }
    drawable.push({
      id: z.id,
      label: z.label,
      pts,
      obstacles: Array.isArray(z.obstacles) ? z.obstacles : [],
      roofType: z.roofType,
      pitchDeg: z.pitchDeg,
      facingAzimuthDeg: z.facingAzimuthDeg,
      neededPanels: z.neededPanels,
    })
  }

  if (drawable.length === 0) return null
  // Boîte dégénérée (tous points identiques) → non dessinable proprement.
  if (!(maxLng > minLng) && !(maxLat > minLat)) return null
  return { zones: drawable, bbox: { minLng, maxLng, minLat, maxLat } }
}

export default function RoofViewer({ layout, imageUrl = null, className = '' }) {
  const geom = extractGeometry(layout)

  // — État vide : pas de géométrie exploitable (et pas d'image non plus). —
  if (!geom && !imageUrl) {
    return (
      <div
        className={`rounded-lg border border-dashed border-border bg-muted/30 p-6 text-center text-sm text-muted-foreground ${className}`}
        data-testid="roofviewer-empty"
      >
        Aucun plan de toiture enregistré pour ce devis.
      </div>
    )
  }

  // Projection lng/lat → coordonnées SVG (0..W, 0..H), latitude inversée
  // (l'axe Y du SVG descend). Marge intérieure pour ne pas coller aux bords.
  const W = 480
  const H = 320
  const PAD = 16

  let project = null
  let panelsTotal = 0
  let zoneSummaries = []
  if (geom) {
    const { minLng, maxLng, minLat, maxLat } = geom.bbox
    const spanLng = Math.max(maxLng - minLng, 1e-9)
    const spanLat = Math.max(maxLat - minLat, 1e-9)
    // Échelle uniforme (préserve les proportions) sur la plus contraignante
    // des deux dimensions.
    const scale = Math.min((W - 2 * PAD) / spanLng, (H - 2 * PAD) / spanLat)
    const drawnW = spanLng * scale
    const drawnH = spanLat * scale
    const offX = PAD + (W - 2 * PAD - drawnW) / 2
    const offY = PAD + (H - 2 * PAD - drawnH) / 2
    project = (lng, lat) => [
      offX + (lng - minLng) * scale,
      // latitude croissante = vers le haut → on inverse.
      offY + (maxLat - lat) * scale,
    ]
    zoneSummaries = geom.zones.map((z, i) => {
      const n = Number(z.neededPanels)
      if (Number.isFinite(n)) panelsTotal += n
      return {
        key: z.id ?? i,
        label: z.label || `Zone ${i + 1}`,
        roofType: ROOF_TYPE_LABEL[z.roofType] ?? z.roofType ?? '—',
        pitch: Number.isFinite(Number(z.pitchDeg)) ? `${Math.round(Number(z.pitchDeg))}°` : null,
        orientation: azimuthLabel(z.facingAzimuthDeg),
        panels: Number.isFinite(n) ? n : null,
      }
    })
  }

  return (
    <div className={className} data-testid="roofviewer">
      {/* Aperçu image (snapshot 3D) prioritaire si présent. */}
      {imageUrl && (
        <img
          src={imageUrl}
          alt="Aperçu 3D de la toiture"
          className="mb-3 w-full rounded-lg border border-border object-contain"
          loading="lazy"
        />
      )}

      {geom && project && (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full rounded-lg border border-border bg-muted/20"
          role="img"
          aria-label="Plan de la toiture (lecture seule)"
          data-testid="roofviewer-svg"
        >
          {geom.zones.map((z, i) => {
            const poly = z.pts.map(([lng, lat]) => project(lng, lat).join(',')).join(' ')
            return (
              <g key={z.id ?? i}>
                <polygon
                  points={poly}
                  fill="hsl(var(--primary) / 0.15)"
                  stroke="hsl(var(--primary))"
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
                {/* Obstacles (zones d'exclusion) — petits rectangles projetés. */}
                {(z.obstacles ?? []).map((o, j) => {
                  const cLng = Number(o.centerLng); const cLat = Number(o.centerLat)
                  if (!Number.isFinite(cLng) || !Number.isFinite(cLat)) return null
                  const wDeg = (Number(o.widthM) || 1) / M_PER_DEG_LAT
                  const lDeg = (Number(o.lengthM) || 1) / M_PER_DEG_LAT
                  const [x1, y1] = project(cLng - wDeg / 2, cLat + lDeg / 2)
                  const [x2, y2] = project(cLng + wDeg / 2, cLat - lDeg / 2)
                  return (
                    <rect
                      key={o.id ?? j}
                      x={Math.min(x1, x2)}
                      y={Math.min(y1, y2)}
                      width={Math.abs(x2 - x1)}
                      height={Math.abs(y2 - y1)}
                      fill="hsl(var(--destructive) / 0.25)"
                      stroke="hsl(var(--destructive))"
                      strokeWidth="1"
                    />
                  )
                })}
              </g>
            )
          })}
        </svg>
      )}

      {/* Résumé lecture seule des zones. */}
      {zoneSummaries.length > 0 && (
        <div className="mt-3 space-y-2">
          {panelsTotal > 0 && (
            <p className="text-sm font-medium">
              {panelsTotal} panneau{panelsTotal > 1 ? 'x' : ''} · {zoneSummaries.length} zone{zoneSummaries.length > 1 ? 's' : ''}
            </p>
          )}
          <ul className="space-y-1 text-xs text-muted-foreground">
            {zoneSummaries.map(z => (
              <li key={z.key} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="font-medium text-foreground">{z.label}</span>
                <span>· {z.roofType}</span>
                {z.pitch && <span>· {z.pitch}</span>}
                {z.orientation && <span>· {z.orientation}</span>}
                {z.panels != null && <span>· {z.panels} panneau{z.panels > 1 ? 'x' : ''}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
