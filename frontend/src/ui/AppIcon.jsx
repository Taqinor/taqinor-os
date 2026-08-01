// ODY9 — Iconographie d'apps signature : UN composant, QUATRE surfaces.
// ----------------------------------------------------------------------------
// L'antidote au piège Odoo « incohérence inter-apps » : jusqu'ici le Menu
// d'accueil, le lanceur (VX9), les épinglés (VX10) et l'écran Applications
// (ODX5) dessinaient CHACUN leur propre pastille — tailles, arrondis et fonds
// différents, et même des GLYPHES différents pour la même app (l'écran
// Applications résolvait l'icône depuis le manifest backend, les trois autres
// depuis le `module.config` frontend).
//
// Ce composant est PUREMENT présentationnel : il reçoit le nœud d'icône déjà
// résolu, jamais une clé de module — c'est `lib/apps/appIcon.js` qui résout la
// clé, et il le fait depuis la MÊME source que `useInstalledApps()` (ODY1).
// Résultat : les quatre surfaces affichent forcément le même glyphe. Garder
// `ui/` sans dépendance vers `router/` évite aussi un cycle d'import
// (ui → router → features/*/module.config → ui).
//
// Forme : conteneur « superellipse » (arrondi dérivé de `--radius`, jamais un
// rayon en dur), fond = teinte de l'accent module (VX8) à ~12 %, glyphe à
// l'accent plein — contraste AA en clair comme en sombre puisque l'accent est
// une couleur de premier plan du thème, jamais un gris délavé.
import { cn } from '../lib/cn'

// Tailles du contrat ODY9 : 64 / 56 / 48 px.
// `xs` (30 px) est l'exception documentée du RAIL compact des épinglés (VX10,
// `.sidebar-pinned-item` fait 1,9 rem) : le contrat « une seule pastille pour
// toutes les surfaces » ne tenait pas si ce rail devait garder son propre
// composant. Ne pas l'utiliser ailleurs.
const SIZES = { lg: 64, md: 56, sm: 48, xs: 30 }

/**
 * AppIcon — pastille d'application.
 *
 * @param {object}  props
 * @param {import('react').ReactNode} props.icon  nœud d'icône déjà résolu
 *   (élément lucide du `module.config`, cf. `lib/apps/appIcon.js`).
 * @param {string} [props.accent]  clé d'accent module VX8 ('azur', 'brass'…).
 * @param {string} [props.label]   nom de l'app — sert au titre/alt éventuel.
 * @param {'lg'|'md'|'sm'} [props.size='md']
 * @param {boolean} [props.interactive=false]  active le survol (élévation +
 *   liseré accent plein). Laisser à `false` quand la pastille est DANS un
 *   bouton qui porte déjà son propre survol.
 */
export function AppIcon({
  icon, accent, label, size = 'md', interactive = false, className, style, ...props
}) {
  const px = SIZES[size] ?? SIZES.md
  return (
    <span
      className={cn('app-icon', interactive && 'app-icon--interactive', className)}
      style={{
        '--app-icon-size': `${px}px`,
        ...(accent ? { '--module-accent': `var(--module-accent-${accent})` } : null),
        ...style,
      }}
      data-app-icon-size={size}
      aria-hidden={label ? undefined : 'true'}
      role={label ? 'img' : undefined}
      aria-label={label || undefined}
      {...props}
    >
      <span className="app-icon-glyph" aria-hidden="true">{icon}</span>
    </span>
  )
}

export default AppIcon
