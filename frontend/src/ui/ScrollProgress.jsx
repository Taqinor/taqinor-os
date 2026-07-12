import { cn } from '../lib/cn'

/* ============================================================================
   VX136 — Barre de progression de scroll NATIVE (2026). `animation-timeline:
   scroll(nearest)` lie la largeur de la barre (scaleX 0→1) au scroll du plus
   proche ancêtre défilant — compositor thread, ZÉRO JS d'orchestration
   (aucun listener `scroll`, aucun `requestAnimationFrame`). Pensée pour les
   deux formulaires-fleuves (LeadForm, DevisGenerator) : à placer en premier
   enfant du conteneur qui défile réellement (ici `.modal-body`, overflow-y
   auto — PAS la fenêtre).

   Progressive enhancement pur (le `@supports` vit dans index.css) :
   Firefox/Safari < 18 ne rendent simplement pas l'animation — repli une
   piste statique (scaleX(0)) sans erreur ni saut de mise en page. Sous
   reduced-motion, la timeline est désactivée (index.css).
   ========================================================================== */
export function ScrollProgress({ className }) {
  return <div aria-hidden="true" className={cn('scroll-progress-bar', className)} />
}

export default ScrollProgress
