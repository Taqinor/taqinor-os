import { useEffect, useRef } from 'react'
import {
  shouldIgnorePanStart,
  isPannablePointerType,
  exceedsPanThreshold,
} from './panScrollPredicates'

/**
 * LB11 — Drag-to-pan sur l'espace vide du board (Trello,
 * docs/design/leads-board-blueprint.md D2) : cliquer-tirer le fond de
 * `.kb-board` fait défiler horizontalement — exactement la plainte
 * fondatrice (« quand je veux scroller à droite je dois défiler tout en
 * bas »). Shift+molette reste natif et gratuit (aucun handler wheel ici).
 *
 * N'entre JAMAIS en conflit avec le PointerSensor dnd-kit du drag de carte :
 * ses propres listeners vivent sur `.kb-card`/`.kb-drag-wrap`, ignorés ici
 * via `shouldIgnorePanStart` (panScrollPredicates.js, testé `node --test`
 * indépendamment). Écouteurs natifs posés directement sur le nœud DOM
 * (jamais de JSX à câbler) — retourne un `ref` à poser sur `.kb-board`.
 *
 * Listeners natifs isolés sur le nœud (jamais sur `document`) : pas de fuite
 * inter-vues, cleanup automatique au démontage.
 */
export function usePanScroll() {
  const boardRef = useRef(null)
  // Mutable, PAS de state React : chaque pointermove pendant un pan ne doit
  // JAMAIS re-render KanbanView (perf — même esprit que LB6/mémoïsation).
  const panRef = useRef(null)

  useEffect(() => {
    const board = boardRef.current
    if (!board) return undefined

    const onPointerDown = (e) => {
      if (e.button !== 0) return
      if (!isPannablePointerType(e.pointerType)) return
      if (shouldIgnorePanStart(e.target)) return
      panRef.current = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        scrollLeft: board.scrollLeft,
        armed: false,
      }
    }

    const onPointerMove = (e) => {
      const p = panRef.current
      if (!p || p.pointerId !== e.pointerId) return
      const dx = e.clientX - p.startX
      const dy = e.clientY - p.startY
      if (!p.armed) {
        if (!exceedsPanThreshold(dx, dy)) return
        p.armed = true
        try { board.setPointerCapture(e.pointerId) } catch { /* déjà relâché */ }
        board.classList.add('kb-board-panning')
      }
      board.scrollLeft = p.scrollLeft - dx
    }

    const release = (e) => {
      const p = panRef.current
      if (!p || p.pointerId !== e.pointerId) return
      if (p.armed) {
        try {
          if (board.hasPointerCapture?.(e.pointerId)) board.releasePointerCapture(e.pointerId)
        } catch { /* déjà relâché */ }
      }
      board.classList.remove('kb-board-panning')
      panRef.current = null
    }

    board.addEventListener('pointerdown', onPointerDown)
    board.addEventListener('pointermove', onPointerMove)
    board.addEventListener('pointerup', release)
    board.addEventListener('pointercancel', release)
    return () => {
      board.removeEventListener('pointerdown', onPointerDown)
      board.removeEventListener('pointermove', onPointerMove)
      board.removeEventListener('pointerup', release)
      board.removeEventListener('pointercancel', release)
    }
  }, [])

  return boardRef
}

export default usePanScroll
