/* VX154 — Mot-symbole Taqinor : le soleil rayonnant à éclair azur du
   public/favicon.svg, porté dans l'app React et TOKENISÉ pour un rendu correct
   en clair comme en sombre :
     • rayons + disque solaire = var(--primary) (le brass de marque)
     • éclair                  = var(--info)    (l'azur de marque)
   Props :
     • size    — côté du glyphe en px (défaut 20)
     • animate — active la séquence d'illumination des rayons (voir SolarLoader
                 + keyframe `sun-rise` dans index.css) ; statique par défaut
     • title   — si fourni, le glyphe devient role="img" avec ce nom accessible ;
                 sinon il est purement décoratif (aria-hidden). */

// 12 rayons répartis tous les 30° (géométrie identique au favicon).
const RAYS = Array.from({ length: 12 }, (unused, i) => i * 30)

export default function TaqinorMark({ size = 20, animate = false, title, className = '', ...rest }) {
  const decorative = !title
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={`taqinor-mark${animate ? ' taqinor-mark--animate' : ''}${className ? ` ${className}` : ''}`}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative ? 'true' : undefined}
      aria-label={decorative ? undefined : title}
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      <g stroke="var(--primary)" strokeWidth="3.4" strokeLinecap="round">
        {RAYS.map((deg, i) => (
          <line
            key={deg}
            className="taqinor-ray"
            style={{ '--ray-i': i }}
            x1="32"
            y1="3"
            x2="32"
            y2="10"
            transform={`rotate(${deg} 32 32)`}
          />
        ))}
      </g>
      <circle cx="32" cy="32" r="17.5" fill="var(--primary)" />
      {/* Éclair azur (coords dérivées du favicon translate(13.4 13.4) scale(1.16)). */}
      <polygon
        points="33.5 18 21.5 34.3 32 34.3 30.5 45.9 42.4 29.6 32 29.6"
        fill="var(--info)"
      />
    </svg>
  )
}
