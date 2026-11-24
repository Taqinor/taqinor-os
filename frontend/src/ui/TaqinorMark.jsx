/* VX154 — Mot-symbole Taqinor : l'emblème OFFICIEL (celui du devis et du site
   public, `apps/web/public/favicon.svg`) porté dans l'app React — un seul logo
   partout (décision fondateur, 24/11/2026) :
     • 8 rayons dorés (#FEC811) tous les 45°, bouts ronds
     • disque solaire doré (#FEC811)
     • éclair bleu nuit (#022F53), posé SUR le disque doré : lisible en clair
       comme en sombre, donc les couleurs sont fixes (pas de variable de thème).
   Props :
     • size    — côté du glyphe en px (défaut 20)
     • animate — active la séquence d'illumination des rayons (voir SolarLoader
                 + keyframe `sun-rise` dans index.css) ; statique par défaut
     • title   — si fourni, le glyphe devient role="img" avec ce nom accessible ;
                 sinon il est purement décoratif (aria-hidden). */

// 8 rayons répartis tous les 45° (géométrie identique au favicon officiel).
const RAYS = Array.from({ length: 8 }, (unused, i) => i * 45)

export default function TaqinorMark({ size = 20, animate = false, title, className = '', ...rest }) {
  const decorative = !title
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={`taqinor-mark${animate ? ' taqinor-mark--animate' : ''}${className ? ` ${className}` : ''}`}
      role={decorative ? undefined : 'img'}
      aria-hidden={decorative ? 'true' : undefined}
      aria-label={decorative ? undefined : title}
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      <g stroke="#FEC811" strokeWidth="6" strokeLinecap="round">
        {RAYS.map((deg, i) => (
          <line
            key={deg}
            className="taqinor-ray"
            style={{ '--ray-i': i }}
            x1="50"
            y1="15"
            x2="50"
            y2="3"
            transform={`rotate(${deg} 50 50)`}
          />
        ))}
      </g>
      <circle cx="50" cy="50" r="28" fill="#FEC811" />
      <path d="M52.1 28.8 L31.1 54.2 L50 54.2 L47.9 71 L68.9 45.8 L50 45.8 Z" fill="#022F53" />
    </svg>
  )
}
