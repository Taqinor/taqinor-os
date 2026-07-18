/* ============================================================================
   ADSDEEP36 — Grille heure×jour du dayparting.
   ----------------------------------------------------------------------------
   Représentation PARTAGÉE avec le backend (``dayparting.py``) : 7 jours
   (lundi→dimanche) × 24 heures, 1 = diffusion autorisée. Une case par heure ⇒
   toute borne est, PAR CONSTRUCTION, toujours à l'heure pleine (aucune saisie
   de minutes). Contrôlé (``value``/``onChange``) — l'écran appelant décide du
   chemin (natif lifetime-budget vs interne quotidien, ADSDEEP36) et de l'envoi.
   ========================================================================== */

import { DP_DAYS, DP_DAY_LABELS, emptyGrid } from './adsengine'

export default function DaypartingGrid({ value, onChange, readOnly = false }) {
  const grid = value || emptyGrid()

  const toggle = (day, hour) => {
    if (readOnly) return
    const next = { ...grid, [day]: grid[day].map((v, h) => (h === hour ? (v ? 0 : 1) : v)) }
    onChange?.(next)
  }

  return (
    <div className="ae-dayparting-grid" data-testid="dp-grid" role="table" aria-label="Horaire de diffusion par heure et par jour">
      <div role="row" style={{ display: 'grid', gridTemplateColumns: '3rem repeat(24, 1.6rem)', gap: 2 }}>
        <span role="columnheader" />
        {Array.from({ length: 24 }, (_, h) => (
          <span key={h} role="columnheader" style={{ fontSize: '0.65rem', textAlign: 'center', color: '#64748b' }}>
            {h}
          </span>
        ))}
      </div>
      {DP_DAYS.map(day => (
        <div key={day} role="row" style={{ display: 'grid', gridTemplateColumns: '3rem repeat(24, 1.6rem)', gap: 2 }}>
          <span role="rowheader" style={{ fontSize: '0.75rem', color: '#334155', alignSelf: 'center' }}>
            {DP_DAY_LABELS[day]}
          </span>
          {grid[day].map((allowed, hour) => (
            <button
              key={hour}
              type="button"
              role="cell"
              data-testid={`dp-cell-${day}-${hour}`}
              aria-pressed={!!allowed}
              aria-label={`${DP_DAY_LABELS[day]} ${hour}h — ${allowed ? 'autorisé' : 'bloqué'}`}
              disabled={readOnly}
              onClick={() => toggle(day, hour)}
              style={{
                width: '1.6rem', height: '1.6rem', padding: 0, border: '1px solid #e2e8f0',
                borderRadius: 3, cursor: readOnly ? 'default' : 'pointer',
                background: allowed ? '#4338ca' : '#f1f5f9',
              }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
