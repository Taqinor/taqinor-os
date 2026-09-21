/* ============================================================================
   AOF106 — Un repère d'annotation : cercle rouge + lettre indexée.
   ----------------------------------------------------------------------------
   La LETTRE N'EST PAS STOCKÉE : elle est DÉRIVÉE de la position du repère dans
   la liste (`lettreDe(index)`). C'est ce qui rend la renumérotation cohérente
   après une suppression sans aucun code de renumérotation — supprimer B fait
   mécaniquement de l'ancien C le nouveau B, sans qu'aucune lettre ne soit
   réécrite nulle part (le bug classique de ce genre d'outil).

   Les coordonnées sont en UNITÉS DE VIEWBOX (0..1000), jamais en pixels :
   l'annotation reste nette à n'importe quelle résolution d'export, et un
   changement de taille d'écran ne déplace aucun repère.

   Accessibilité (gate AOF188) : chaque repère est un élément focusable avec un
   nom accessible, entièrement pilotable au clavier — flèches pour déplacer,
   `+`/`-` pour redimensionner, `Suppr` pour supprimer. Un annotateur qui
   n'existe qu'à la souris ne passe pas le gate.
   ========================================================================== */

// Lettre indexée : A…Z, puis AA, AB… (jamais un index numérique nu).
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function lettreDe(index) {
  let n = index
  let out = ''
  do {
    out = String.fromCharCode(65 + (n % 26)) + out
    n = Math.floor(n / 26) - 1
  } while (n >= 0)
  return out
}

export const PAS_DEPLACEMENT = 10 // unités de viewBox
export const PAS_TAILLE = 4
export const RAYON_MIN = 8
export const RAYON_MAX = 200

const clamp = (v, min, max) => Math.min(Math.max(v, min), max)

export function RepereMarker({
  repere,
  lettre,
  selectionne = false,
  onSelect,
  onDeplacer,
  onRedimensionner,
  onSupprimer,
  onDebutGlisser,
}) {
  const gererClavier = (e) => {
    const pas = e.shiftKey ? PAS_DEPLACEMENT * 5 : PAS_DEPLACEMENT
    switch (e.key) {
      case 'ArrowLeft': onDeplacer?.(repere.id, { dx: -pas, dy: 0 }); break
      case 'ArrowRight': onDeplacer?.(repere.id, { dx: pas, dy: 0 }); break
      case 'ArrowUp': onDeplacer?.(repere.id, { dx: 0, dy: -pas }); break
      case 'ArrowDown': onDeplacer?.(repere.id, { dx: 0, dy: pas }); break
      case '+':
      case '=': onRedimensionner?.(repere.id, PAS_TAILLE); break
      case '-': onRedimensionner?.(repere.id, -PAS_TAILLE); break
      case 'Delete':
      case 'Backspace': onSupprimer?.(repere.id); break
      default: return
    }
    e.preventDefault()
    e.stopPropagation()
  }

  return (
    <g
      data-ao-repere={lettre}
      role="button"
      tabIndex={0}
      aria-label={`Repère ${lettre}`}
      aria-pressed={selectionne}
      onKeyDown={gererClavier}
      onClick={(e) => { e.stopPropagation(); onSelect?.(repere.id) }}
      onPointerDown={(e) => { e.stopPropagation(); onDebutGlisser?.(repere.id, e) }}
      style={{ cursor: 'grab' }}
    >
      <circle
        cx={repere.x}
        cy={repere.y}
        r={repere.r}
        fill="none"
        style={{ stroke: 'var(--destructive)' }}
        strokeWidth={selectionne ? 6 : 4}
      />
      <text
        x={repere.x}
        y={repere.y + repere.r + 26}
        textAnchor="middle"
        style={{ fill: 'var(--destructive)', fontSize: '26px', fontWeight: 700 }}
      >
        {lettre}
      </text>
    </g>
  )
}

// Applique un déplacement/redimensionnement en restant dans le cadre.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function deplacer(repere, { dx, dy }, taille) {
  return {
    ...repere,
    x: clamp(repere.x + dx, 0, taille),
    y: clamp(repere.y + dy, 0, taille),
  }
}

// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable), même motif que DevisTab.devisTrackCurrent
export function redimensionner(repere, delta) {
  return { ...repere, r: clamp(repere.r + delta, RAYON_MIN, RAYON_MAX) }
}

export default RepereMarker
