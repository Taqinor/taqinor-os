import TaqinorMark from './TaqinorMark'

/* VX154 — Attente SIGNÉE : au lieu d'un spinner gris anonyme, le mot-symbole
   Taqinor dont les rayons s'illuminent en séquence (CSS pur, keyframe `sun-rise`
   dans index.css). Figé sur un soleil pleinement éclairé sous
   prefers-reduced-motion (règle dédiée dans index.css). RÉSERVÉ aux attentes
   plein-écran / transitions de route — JAMAIS les spinners inline de bouton
   (garder <Spinner> pour ceux-là). */
export default function SolarLoader({ size = 40, label = 'Chargement…', className = '' }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`solar-loader${className ? ` ${className}` : ''}`}
    >
      <TaqinorMark size={size} animate />
      <span className="sr-only">{label}</span>
    </div>
  )
}
