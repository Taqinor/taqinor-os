import {
  forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useReducer, useRef, useState,
} from 'react'
import { Maximize2, ZoomIn, ZoomOut } from 'lucide-react'
import { IconButton } from '../../../ui'
import {
  agregerParRangee,
  creerViewport,
  doitAgreger,
  ecranVersMonde,
  formatMetres,
  graduations,
  mondeVersEcran,
  pasDeGrille,
  reduireViewport,
  viewBoxDe,
} from './useViewport'

/* ============================================================================
   AOF74 — Canvas SVG en MÈTRES : viewBox, pan, zoom, grille, règles.
   ----------------------------------------------------------------------------
   ZÉRO nouvelle dépendance npm (contrainte VX) : pan/zoom par matrice de vue
   pure (`useViewport.js`, testé au node), interactions en pointer events natifs.

   Pourquoi du SVG React plutôt qu'un `<canvas>` : chaque élément dessiné est un
   NŒUD DOM, donc la sélection, le survol et le focus clavier sont gratuits, les
   hooks `data-ao-*` du contrat AOF8 sont posables, et l'export en image
   (AOF75) sérialise directement le nœud `<svg>` — d'où la `ref` transmise.

   Le repère monde est y↑ (nord) alors que SVG est y↓ : le groupe racine porte
   `scale(1,-1)` et le `viewBox` est calculé en conséquence (`viewBoxDe`). Toute
   la géométrie passée en `children` est donc en MÈTRES, x est→ / y nord↑, sans
   conversion à la charge de l'appelant. Corollaire assumé : aucun `<text>` dans
   ce groupe (il sortirait en miroir) — les libellés vivent dans les règles HTML
   et dans la barre d'état.

   Limite de volume traitée : au-delà de `SEUIL_AGREGATION` tables ET tant que
   le zoom reste large, les tables sont agrégées en UN `<path>` par rangée
   (2 000 tables → ~40 nœuds) ; le rendu table-par-table ne revient qu'au zoom.
   ========================================================================== */

const PAS_CLAVIER_PX = 40
const FACTEUR_BOUTON = 1.3

function tailleDe(el) {
  const r = el.getBoundingClientRect()
  return { largeur: r.width, hauteur: r.height }
}

// Chemin unique regroupant toutes les lignes d'une grille (1 nœud DOM au lieu
// d'un par ligne — c'est ce qui rend la grille gratuite au pan).
function cheminGrille(vp, xs, ys) {
  const parts = []
  for (const x of xs) parts.push(`M${x} ${vp.y}V${vp.y + vp.h}`)
  for (const y of ys) parts.push(`M${vp.x} ${y}H${vp.x + vp.l}`)
  return parts.join('')
}

export const CanvasSvg = forwardRef(function CanvasSvg({
  bbox = null,
  tables = [],
  seuilAgregation,
  grille = true,
  regles = true,
  onCurseur,
  onViewportChange,
  ariaLabel = 'Plan — canvas en mètres',
  children,
  className = '',
}, ref) {
  const conteneurRef = useRef(null)
  const svgRef = useRef(null)
  useImperativeHandle(ref, () => svgRef.current, [])

  const [etat, dispatch] = useReducer(reduireViewport, undefined, () => ({
    viewport: creerViewport(0, 0, 40, 20),
    taille: { largeur: 0, hauteur: 0 },
  }))
  const { viewport, taille } = etat
  const mesure = taille.largeur > 0 && taille.hauteur > 0

  const [espace, setEspace] = useState(false)
  const pointeurs = useRef(new Map())
  const dernierPan = useRef(null)
  const dernierPinch = useRef(null)
  const dejaAjuste = useRef(false)

  // ── Mesure de l'élément (ResizeObserver — jamais un listener `resize`) ────
  useEffect(() => {
    const el = conteneurRef.current
    if (!el) return undefined
    dispatch({ type: 'taille', taille: tailleDe(el) })
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(() => dispatch({ type: 'taille', taille: tailleDe(el) }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Premier « ajuster à la vue » dès que la scène ET l'élément sont connus.
  useEffect(() => {
    if (!mesure || !bbox || dejaAjuste.current) return
    dejaAjuste.current = true
    dispatch({ type: 'ajuster', bbox })
  }, [mesure, bbox])

  // La remontée de vue passe par une ref : un parent qui repasse une lambda à
  // chaque rendu ne doit pas relancer l'effet (boucle de rendu garantie).
  const remonterRef = useRef(onViewportChange)
  useEffect(() => { remonterRef.current = onViewportChange })
  useEffect(() => {
    if (mesure) remonterRef.current?.(viewport, taille)
  }, [viewport, taille, mesure])

  const positionLocale = useCallback((e) => {
    const el = svgRef.current
    if (!el) return { x: 0, y: 0 }
    const r = el.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }, [])

  // ── Molette : zoom autour du curseur. Listener NATIF non passif — React
  //    attache `onWheel` en passif, `preventDefault()` y serait ignoré. ──────
  useEffect(() => {
    const el = svgRef.current
    if (!el) return undefined
    const onWheel = (e) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      dispatch({
        type: 'zoom',
        facteur: Math.exp(-e.deltaY * 0.0015),
        ancre: { x: e.clientX - r.left, y: e.clientY - r.top },
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  // ── Pointeurs : pan (barre d'espace / bouton du milieu) et pincement ──────
  const onPointerDown = (e) => {
    pointeurs.current.set(e.pointerId, positionLocale(e))
    // Un doigt sur le FOND panoramique ; un doigt sur une forme appartient à
    // l'outil de dessin (qui vit dans `children`), jamais à la vue.
    const surFond = e.target === svgRef.current
    const panDemande = espace || e.button === 1 || (e.pointerType === 'touch' && surFond)
    if (pointeurs.current.size === 1 && panDemande) {
      dernierPan.current = positionLocale(e)
      e.currentTarget.setPointerCapture?.(e.pointerId)
    }
    if (pointeurs.current.size === 2) {
      dernierPan.current = null
      dernierPinch.current = null
    }
  }

  const onPointerMove = (e) => {
    const p = positionLocale(e)
    if (pointeurs.current.has(e.pointerId)) pointeurs.current.set(e.pointerId, p)
    if (mesure) onCurseur?.(ecranVersMonde(p, viewport, taille))

    if (pointeurs.current.size === 2) {
      const [a, b] = [...pointeurs.current.values()]
      const distance = Math.hypot(a.x - b.x, a.y - b.y)
      const milieu = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
      const precedent = dernierPinch.current
      if (precedent && precedent.distance > 0 && distance > 0) {
        dispatch({ type: 'zoom', facteur: distance / precedent.distance, ancre: milieu })
        dispatch({
          type: 'deplacer',
          dx: milieu.x - precedent.milieu.x,
          dy: milieu.y - precedent.milieu.y,
        })
      }
      dernierPinch.current = { distance, milieu }
      return
    }

    if (dernierPan.current) {
      dispatch({ type: 'deplacer', dx: p.x - dernierPan.current.x, dy: p.y - dernierPan.current.y })
      dernierPan.current = p
    }
  }

  const finPointeur = (e) => {
    pointeurs.current.delete(e.pointerId)
    if (pointeurs.current.size < 2) dernierPinch.current = null
    if (pointeurs.current.size === 0) dernierPan.current = null
  }

  const onPointerLeave = (e) => {
    finPointeur(e)
    onCurseur?.(null)
  }

  // ── Clavier : flèches = pan, +/− = zoom, 0 = ajuster, espace = main ───────
  const onKeyDown = (e) => {
    const bond = e.shiftKey ? PAS_CLAVIER_PX * 4 : PAS_CLAVIER_PX
    const pans = {
      ArrowLeft: { dx: bond, dy: 0 },
      ArrowRight: { dx: -bond, dy: 0 },
      ArrowUp: { dx: 0, dy: bond },
      ArrowDown: { dx: 0, dy: -bond },
    }
    if (pans[e.key]) {
      e.preventDefault()
      dispatch({ type: 'deplacer', ...pans[e.key] })
      return
    }
    if (e.key === '+' || e.key === '=') {
      e.preventDefault()
      dispatch({ type: 'zoom', facteur: FACTEUR_BOUTON })
    } else if (e.key === '-' || e.key === '_') {
      e.preventDefault()
      dispatch({ type: 'zoom', facteur: 1 / FACTEUR_BOUTON })
    } else if (e.key === '0' && bbox) {
      e.preventDefault()
      dispatch({ type: 'ajuster', bbox })
    } else if (e.key === ' ') {
      e.preventDefault()
      setEspace(true)
    }
  }

  const onKeyUp = (e) => {
    if (e.key === ' ') setEspace(false)
  }

  // ── Grille adaptative + règles graduées ──────────────────────────────────
  const pas = mesure ? pasDeGrille(viewport, taille) : 1
  const { grilleMineure, grilleMajeure, ticksX, ticksY, pasRegle } = useMemo(() => {
    if (!mesure || !grille) {
      const pasR = mesure ? pasDeGrille(viewport, taille, 110) : 1
      return {
        grilleMineure: '',
        grilleMajeure: '',
        ticksX: mesure ? graduations(viewport, 'x', pasR) : [],
        ticksY: mesure ? graduations(viewport, 'y', pasR) : [],
        pasRegle: pasR,
      }
    }
    const xs = graduations(viewport, 'x', pas)
    const ys = graduations(viewport, 'y', pas)
    const majeur = pas * 5
    const pasR = pasDeGrille(viewport, taille, 110)
    return {
      grilleMineure: cheminGrille(viewport, xs, ys),
      grilleMajeure: cheminGrille(
        viewport,
        graduations(viewport, 'x', majeur),
        graduations(viewport, 'y', majeur),
      ),
      ticksX: graduations(viewport, 'x', pasR),
      ticksY: graduations(viewport, 'y', pasR),
      pasRegle: pasR,
    }
  }, [viewport, taille, mesure, grille, pas])

  // ── Niveau de détail des tables PV ───────────────────────────────────────
  const agrege = mesure && doitAgreger(tables.length, viewport, taille, seuilAgregation)
  const chemins = useMemo(
    () => (agrege
      ? agregerParRangee(tables).map((r) => ({ id: `rangee-${r.rangee}`, d: r.d }))
      : tables),
    [agrege, tables],
  )

  return (
    <div ref={conteneurRef} className={`relative h-full w-full ${className}`.trim()}>
      <svg
        ref={svgRef}
        data-ao-canvas=""
        tabIndex={0}
        aria-label={ariaLabel}
        viewBox={viewBoxDe(viewport)}
        preserveAspectRatio="xMidYMid meet"
        className={`h-full w-full touch-none select-none focus-ring ${espace ? 'cursor-grab' : ''}`.trim()}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={finPointeur}
        onPointerCancel={finPointeur}
        onPointerLeave={onPointerLeave}
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
      >
        {/* Monde y↑ → SVG y↓ : le SEUL endroit où la convention bascule. */}
        <g transform="scale(1,-1)">
          {grille && (
            <>
              <path
                d={grilleMineure}
                fill="none"
                stroke="currentColor"
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
                className="text-border/50"
              />
              <path
                d={grilleMajeure}
                fill="none"
                stroke="currentColor"
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
                className="text-border"
              />
            </>
          )}
          {chemins.map((c) => (
            <path
              key={c.id}
              id={c.id}
              d={c.d}
              className="fill-primary/60 stroke-primary"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {children}
        </g>
      </svg>

      {/* Règles graduées — en HTML : du texte dans le groupe `scale(1,-1)`
          sortirait en miroir. */}
      {regles && mesure && (
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          {ticksX.map((x) => (
            <span
              key={`rx-${x}`}
              className="absolute top-0 -translate-x-1/2 border-l border-border/70 pl-1 text-[10px] leading-4 text-muted-foreground"
              style={{ left: `${mondeVersEcran({ x, y: 0 }, viewport, taille).x}px` }}
            >
              {formatMetres(x, pasRegle)}
            </span>
          ))}
          {ticksY.map((y) => (
            <span
              key={`ry-${y}`}
              className="absolute left-0 -translate-y-1/2 border-t border-border/70 pl-1 text-[10px] leading-4 text-muted-foreground"
              style={{ top: `${mondeVersEcran({ x: 0, y }, viewport, taille).y}px` }}
            >
              {formatMetres(y, pasRegle)}
            </span>
          ))}
        </div>
      )}

      {/* Commandes de vue — le clavier fait la même chose (flèches, +/−, 0). */}
      <div className="absolute bottom-2 right-2 flex flex-col gap-1">
        <IconButton
          label="Zoom avant"
          variant="outline"
          size="sm"
          onClick={() => dispatch({ type: 'zoom', facteur: FACTEUR_BOUTON })}
        >
          <ZoomIn />
        </IconButton>
        <IconButton
          label="Zoom arrière"
          variant="outline"
          size="sm"
          onClick={() => dispatch({ type: 'zoom', facteur: 1 / FACTEUR_BOUTON })}
        >
          <ZoomOut />
        </IconButton>
        <IconButton
          label="Ajuster à la vue"
          variant="outline"
          size="sm"
          disabled={!bbox}
          onClick={() => bbox && dispatch({ type: 'ajuster', bbox })}
        >
          <Maximize2 />
        </IconButton>
      </div>
    </div>
  )
})

export default CanvasSvg
