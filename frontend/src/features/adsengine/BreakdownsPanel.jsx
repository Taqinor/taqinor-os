import { useEffect, useState, useMemo, useCallback } from 'react'
import { Users, LayoutGrid, MapPin, Clock } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { formatMAD, formatNumber } from './adsengine'
import DataWindowNotice from './DataWindowNotice'

/* ============================================================================
   ADSDEEP10 — Panneau « Audience & diffusion » (onglet du détail campagne/ad).
   ----------------------------------------------------------------------------
   Consomme l'endpoint breakdowns (ADSDEEP9) et rend quatre vues :
   - barres ÂGE × GENRE ;
   - split PLACEMENTS (Insta/FB, reels/feed/stories) ;
   - top RÉGIONS ;
   - heatmap HEURE (0-23).
   Toutes les données viennent de l'API (mockée en test) — jamais inventées.
   L'objet cible est passé en props (objectType ∈ campaign/adset/ad + objectId).
   ========================================================================== */

const DIMENSIONS = [
  { key: 'age_gender', label: 'Âge × genre', icon: Users },
  { key: 'platform', label: 'Placements', icon: LayoutGrid },
  { key: 'region', label: 'Régions', icon: MapPin },
  { key: 'hourly', label: 'Heures', icon: Clock },
]

function pct(value, max) {
  if (!max) return 0
  return Math.round((Number(value || 0) / max) * 100)
}

export default function BreakdownsPanel({ objectType = 'campaign', objectId }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    if (!objectId) { setRows([]); setLoading(false); return }
    setLoading(true)
    adsengineApi.breakdowns
      .list({ object_type: objectType, object_id: objectId })
      .then((r) => setRows(Array.isArray(r.data) ? r.data : []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false))
  }, [objectType, objectId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const byDimension = useMemo(() => {
    const map = { age_gender: [], platform: [], region: [], hourly: [] }
    for (const row of rows) {
      if (map[row.dimension]) map[row.dimension].push(row)
    }
    return map
  }, [rows])

  if (loading) {
    return <div data-testid="ae-breakdowns-loading">Chargement…</div>
  }

  const hasAny = rows.length > 0

  return (
    <div data-testid="ae-breakdowns-panel">
      <h3>Audience &amp; diffusion</h3>
      {/* ADSDEEP66 — les ventilations ne sont synchronisées que sur 28 j. */}
      <DataWindowNotice kind="breakdowns" />
      {!hasAny && (
        <p data-testid="ae-breakdowns-empty">
          Aucune ventilation disponible pour cet objet.
        </p>
      )}

      {DIMENSIONS.map(({ key, label, icon: Icon }) => {
        const items = byDimension[key]
        if (!items || items.length === 0) return null
        const max = Math.max(...items.map((i) => Number(i.impressions || 0)), 1)
        return (
          <section key={key} data-testid={`ae-breakdown-${key}`}>
            <h4>{Icon && <Icon size={16} aria-hidden />} {label}</h4>
            <ul>
              {items.map((item) => (
                <li key={item.id} data-testid={`ae-breakdown-${key}-row`}>
                  <span data-testid="ae-breakdown-key">{item.key}</span>
                  <span
                    data-testid="ae-breakdown-bar"
                    style={{ width: `${pct(item.impressions, max)}%` }}
                  />
                  <span data-testid="ae-breakdown-impressions">
                    {formatNumber(item.impressions || 0)} impressions
                  </span>
                  <span data-testid="ae-breakdown-spend">
                    {formatMAD(item.spend || 0)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
