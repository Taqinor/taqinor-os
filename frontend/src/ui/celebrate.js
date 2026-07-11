// VX40 — Le délice mesuré : UNE SEULE célébration dans toute l'app, réservée
// au passage `envoye → accepte` d'un devis (rare, significatif, lié au
// revenu). Règle Asana : honorer le RARE, jamais gamifier la routine — donc
// pas de lib confetti, pas de composant, pas de réutilisation ailleurs.
//
// `celebrateDealSigned()` pose un burst CSS-only (spans absolus animés
// translate/rotate/fade, 0 dépendance) ancré près du coin où sonner affiche
// ses toasts (bottom-right, cf. ui/Toaster.jsx) — la carte visuelle reste le
// toast `sonner` existant, ce burst n'est qu'un ornement autour de lui.
//
// Statique sous `prefers-reduced-motion: reduce` : on ne pose même pas les
// spans (pas seulement une animation neutralisée) — l'appelant garde son
// `toast.success(...)` habituel, qui reste le seul retour visuel.

const PARTICLE_COUNT = 14
const COLORS = ['var(--primary)', 'var(--info)']
const CONTAINER_ID = 'vx40-deal-signed-burst'

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

// Une seule célébration à la fois : si un burst est déjà en cours, on ne pile
// pas un second conteneur par-dessus (pas de gamification de rechargements
// rapides successifs).
function alreadyRunning() {
  return typeof document !== 'undefined' && !!document.getElementById(CONTAINER_ID)
}

/**
 * celebrateDealSigned — burst ponctuel, une fois par transition envoyé→accepté.
 * N'affiche RIEN sous reduced-motion (l'appelant garde son toast normal) et ne
 * s'affiche JAMAIS au simple rechargement de la liste — appeler UNIQUEMENT
 * depuis le point de confirmation de l'acceptation (SigneDialog / DevisList).
 */
export function celebrateDealSigned() {
  if (typeof document === 'undefined') return
  if (prefersReducedMotion()) return
  if (alreadyRunning()) return

  const container = document.createElement('div')
  container.id = CONTAINER_ID
  container.setAttribute('aria-hidden', 'true')
  container.style.cssText = [
    'position:fixed', 'right:24px', 'bottom:88px', 'width:1px', 'height:1px',
    'pointer-events:none', 'z-index:var(--z-toast, 9999)',
  ].join(';')

  for (let i = 0; i < PARTICLE_COUNT; i += 1) {
    const span = document.createElement('span')
    const angle = (Math.random() * 360).toFixed(1)
    const distance = 60 + Math.round(Math.random() * 70)
    const size = 5 + Math.round(Math.random() * 4)
    const color = COLORS[i % COLORS.length]
    const delay = Math.round(Math.random() * 60)
    span.style.cssText = [
      'position:absolute', 'left:0', 'top:0',
      `width:${size}px`, `height:${size}px`,
      `background:${color}`, 'border-radius:2px',
      `--vx40-angle:${angle}deg`, `--vx40-distance:${distance}px`,
      `animation:vx40-burst 700ms ${delay}ms cubic-bezier(.16,1,.3,1) both`,
    ].join(';')
    container.appendChild(span)
  }

  document.body.appendChild(container)
  window.setTimeout(() => container.remove(), 1000)
}

export default celebrateDealSigned
