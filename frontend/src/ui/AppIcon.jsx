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
// (ui → router → features/*/module.config → ui) : d'où le hachage de variante
// écrit ICI, sans import, plutôt qu'emprunté à `lib/apps/`.
//
// ODY33 — « TUILE RICHE » (fondateur, 2026-08-02 : « les icônes des apps ne
// sont PAS DU TOUT comme celles d'Odoo »). La v1 posait l'accent module à 12 %
// en fond avec un glyphe FILAIRE à l'accent : correct en contraste, mais pâle
// et générique — quarante apps s'y ressemblaient toutes. La v2 rend ce qu'une
// tuile d'app doit être : un REMPLISSAGE de couleur franche et saturée (jetons
// `--app-tile-*`, cf. design/tokens.css), un léger dégradé vertical qui donne
// le relief, une ombre portée douce, et un glyphe BLANC à trait épaissi.
// Forme inchangée : conteneur « superellipse » dont l'arrondi est dérivé de
// `--radius` (jamais un rayon en dur).
import { cn } from '../lib/cn'

// Tailles du contrat ODY9 : 64 / 56 / 48 px.
// `xs` (30 px) est l'exception documentée du RAIL compact des épinglés (VX10,
// `.sidebar-pinned-item` fait 1,9 rem) : le contrat « une seule pastille pour
// toutes les surfaces » ne tenait pas si ce rail devait garder son propre
// composant. Ne pas l'utiliser ailleurs.
const SIZES = { lg: 64, md: 56, sm: 48, xs: 30 }

// ODY33 — chaque voie de couleur (`--app-tile-<accent>-N`) compte 3 variantes
// de teinte (±~9°). Sans cela, les 13 apps « lune » ou les 5 apps « azur »
// seraient rigoureusement identiques côte à côte dans la grille.
const VARIANTES_TUILE = 3

/**
 * varianteTuile — 1, 2 ou 3, DÉTERMINÉ par la clé de module (djb2 32 bits).
 * Jamais aléatoire : la même app garde la même couleur d'une session à l'autre
 * et sur les quatre surfaces ODY9. Sans clé (démo, repli), c'est la variante 1.
 */
export function varianteTuile(cle) {
  if (!cle) return 1
  let h = 5381
  for (let i = 0; i < cle.length; i += 1) {
    h = ((h * 33) ^ cle.charCodeAt(i)) >>> 0
  }
  return (h % VARIANTES_TUILE) + 1
}

/**
 * AppIcon — tuile d'application.
 *
 * @param {object}  props
 * @param {import('react').ReactNode} props.icon  nœud d'icône déjà résolu
 *   (élément lucide du `module.config`, cf. `lib/apps/appIcon.js`).
 * @param {string} [props.accent]  clé d'accent module VX8 ('azur', 'brass'…) —
 *   choisit la VOIE de couleur de la tuile.
 * @param {string} [props.appKey]  clé du module ('crm', 'ventes'…) — choisit la
 *   VARIANTE de teinte dans cette voie. À passer sur toutes les surfaces qui
 *   listent des apps, sinon la même app changerait de nuance d'un écran à
 *   l'autre (ce que ODY9 interdit).
 * @param {string} [props.label]   nom de l'app — sert au titre/alt éventuel.
 * @param {'lg'|'md'|'sm'|'xs'} [props.size='md']
 * @param {boolean} [props.interactive=false]  active le survol (élévation +
 *   micro-agrandissement ; rien sous `prefers-reduced-motion`). Laisser à
 *   `false` quand la pastille est DANS un bouton qui porte déjà son survol.
 */
export function AppIcon({
  icon, accent, appKey, label, size = 'md', interactive = false, className, style, ...props
}) {
  const px = SIZES[size] ?? SIZES.md
  return (
    <span
      className={cn('app-icon', interactive && 'app-icon--interactive', className)}
      style={{
        '--app-icon-size': `${px}px`,
        // `--module-accent` reste posé tel quel : il sert encore aux surfaces
        // qui entourent la pastille (liseré de cellule, survol de tuile).
        // `--app-tile` est le NOUVEAU remplissage ; une clé d'accent inconnue
        // retombe proprement sur la voie graphite.
        ...(accent ? {
          '--module-accent': `var(--module-accent-${accent})`,
          '--app-tile': `var(--app-tile-${accent}-${varianteTuile(appKey)}, var(--app-tile-defaut))`,
        } : null),
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
