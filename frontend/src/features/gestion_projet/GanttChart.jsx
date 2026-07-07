import { useMemo, useRef, useState } from 'react'
import { Flag } from 'lucide-react'
import { formatDate } from '../../lib/format'
import { EmptyState } from '../../ui'
import { timelineBounds, barGeometry, markerGeometry, parseDate } from './gantt'

/* ============================================================================
   UX39 — Gantt CSS/SVG léger (aucune bibliothèque Gantt).
   ----------------------------------------------------------------------------
   Une ligne par tâche : libellé à gauche, barre positionnée par plage de dates
   sur une échelle temporelle commune (calculée par `gantt.js`). Les jalons sont
   des losanges pointés sur la même échelle. Les dépendances sont listées en
   légende (connecteurs SVG évités pour rester lisible et robuste au responsive).
   Une barre « baseline » optionnelle (fantôme) se superpose pour le plan vs réel.
   ========================================================================== */

const TONE_BG = {
  a_faire: 'var(--muted-foreground)',
  en_cours: 'var(--primary)',
  termine: 'var(--success, #16a34a)',
  bloque: 'var(--destructive)',
}

const MS_PER_DAY = 24 * 60 * 60 * 1000
const pad2 = (n) => String(n).padStart(2, '0')
const toISO = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`

// PROJ11 — Barre draggable horizontalement : le déplacement en pixels est
// converti en un nombre de jours entiers (arrondi) via la largeur RÉELLE de la
// piste parente (mesurée au pointerdown), puis
// `onReprogrammer(tache, nouvelleDateDebutISO)` est appelé au relâchement (la
// durée est conservée côté serveur — voir l'action `reprogrammer`).
function DraggableBar({ tache, geo, bg, min, max, onReprogrammer, disabled }) {
  const [dragPx, setDragPx] = useState(0)
  const [dragging, setDragging] = useState(false)
  const startXRef = useRef(0)
  const trackWidthRef = useRef(0)

  const handlePointerDown = (e) => {
    if (disabled || !onReprogrammer) return
    startXRef.current = e.clientX
    trackWidthRef.current = e.currentTarget.parentElement?.getBoundingClientRect().width ?? 0
    setDragging(true)
    e.currentTarget.setPointerCapture?.(e.pointerId)
  }

  const handlePointerMove = (e) => {
    if (!dragging) return
    setDragPx(e.clientX - startXRef.current)
  }

  const handlePointerUp = () => {
    if (!dragging) return
    setDragging(false)
    const trackWidth = trackWidthRef.current
    const currentDragPx = dragPx
    setDragPx(0)
    if (!trackWidth || Math.abs(currentDragPx) < 4) return
    const totalMs = parseDate(max).getTime() - parseDate(min).getTime()
    const deltaMs = (currentDragPx / trackWidth) * totalMs
    const deltaJours = Math.round(deltaMs / MS_PER_DAY)
    if (deltaJours === 0) return
    const debut = parseDate(tache.date_debut_prevue)
    if (!debut) return
    const nouvelleDate = new Date(debut.getTime() + deltaJours * MS_PER_DAY)
    onReprogrammer(tache, toISO(nouvelleDate))
  }

  return (
    <div
      className={`absolute top-0.5 flex h-4 items-center overflow-hidden rounded px-1 text-[10px] leading-none text-white ${onReprogrammer && !disabled ? 'cursor-grab active:cursor-grabbing' : ''}`}
      style={{
        left: `${geo.offsetPct}%`,
        width: `${geo.widthPct}%`,
        backgroundColor: bg,
        transform: dragging ? `translateX(${dragPx}px)` : undefined,
      }}
      title={`${tache.libelle} — ${formatDate(tache.date_debut_prevue)} → ${formatDate(tache.date_fin_prevue)}${onReprogrammer && !disabled ? ' (glisser pour replanifier)' : ''}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      {typeof tache.avancement_pct === 'number' && tache.avancement_pct > 0 ? `${tache.avancement_pct}%` : ''}
    </div>
  )
}

export function GanttChart({
  taches = [],
  jalons = [],
  dependances = [],
  baseline = [],
  onReprogrammer,
  busyTacheId,
}) {
  const bounds = useMemo(() => {
    const bars = [
      ...taches.map((t) => ({
        date_debut: t.date_debut_prevue,
        date_fin: t.date_fin_prevue,
      })),
      ...jalons.map((j) => ({ date_debut: j.date_prevue, date_fin: j.date_prevue })),
      ...baseline.map((b) => ({
        date_debut: b.date_debut_prevue,
        date_fin: b.date_fin_prevue,
      })),
    ]
    return timelineBounds(bars)
  }, [taches, jalons, baseline])

  // Baseline indexée par tâche pour superposition rapide.
  const baseByTache = useMemo(() => {
    const m = {}
    for (const b of baseline) m[b.tache] = b
    return m
  }, [baseline])

  if (!bounds) {
    return (
      <EmptyState
        icon={Flag}
        title="Aucune tâche datée"
        description="Ajoutez des dates de début/fin aux tâches pour afficher le planning."
      />
    )
  }

  const { min, max } = bounds

  return (
    <div className="flex flex-col gap-3">
      {/* En-tête d'échelle : dates min/max */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{formatDate(min)}</span>
        <span>{formatDate(max)}</span>
      </div>

      {/* Lignes de tâches */}
      <div className="flex flex-col gap-1.5" role="list" aria-label="Diagramme de Gantt">
        {taches.map((t) => {
          const geo = barGeometry(t.date_debut_prevue, t.date_fin_prevue, min, max)
          const base = baseByTache[t.id]
          const baseGeo = base
            ? barGeometry(base.date_debut_prevue, base.date_fin_prevue, min, max)
            : null
          const bg = TONE_BG[t.statut] ?? 'var(--primary)'
          return (
            <div key={t.id} className="grid grid-cols-[180px_1fr] items-center gap-2" role="listitem">
              <span className="truncate text-sm" title={t.libelle}>
                {t.code_wbs ? <span className="mr-1 font-mono text-xs text-muted-foreground">{t.code_wbs}</span> : null}
                {t.libelle}
              </span>
              <div className="relative h-5 rounded bg-muted/50">
                {baseGeo && baseGeo.widthPct > 0 && (
                  <div
                    className="absolute top-0 h-5 rounded border border-dashed border-muted-foreground/60"
                    style={{ left: `${baseGeo.offsetPct}%`, width: `${baseGeo.widthPct}%` }}
                    title="Baseline (plan figé)"
                  />
                )}
                {geo.widthPct > 0 && (
                  <DraggableBar
                    tache={t}
                    geo={geo}
                    bg={bg}
                    min={min}
                    max={max}
                    onReprogrammer={onReprogrammer}
                    disabled={busyTacheId === t.id}
                  />
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Jalons */}
      {jalons.length > 0 && (
        <div className="mt-2 grid grid-cols-[180px_1fr] items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Jalons</span>
          <div className="relative h-6">
            {jalons.map((j) => {
              const m = markerGeometry(j.date_prevue, min, max)
              if (!m) return null
              return (
                <span
                  key={j.id}
                  className="absolute top-0 -translate-x-1/2"
                  style={{ left: `${m.leftPct}%` }}
                  title={`${j.libelle} — ${formatDate(j.date_prevue)}`}
                >
                  <Flag className="size-4 text-amber-600" aria-hidden="true" />
                </span>
              )
            })}
          </div>
        </div>
      )}

      {/* Légende des dépendances (connecteurs évités pour la lisibilité) */}
      {dependances.length > 0 && (
        <div className="mt-2 border-t border-border pt-2">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Dépendances</p>
          <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground">
            {dependances.map((d) => (
              <li key={d.id}>
                #{d.predecesseur} → #{d.successeur}
                <span className="ml-1 uppercase">({d.type_dependance})</span>
                {d.lag ? <span className="ml-1">lag {d.lag} j</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default GanttChart
