import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* O165 — Découpage des routes + chargement différé.
 *
 * Ce test verrouille le contrat de code-splitting du routeur par analyse
 * statique de `src/router/index.jsx` plutôt qu'en montant l'arbre complet de
 * l'app (store + Layout + toutes les pages lazy + libs lourdes) dans jsdom :
 *   1. chaque composant de page est chargé via `React.lazy(() => import(...))` ;
 *   2. chaque <route> rend son contenu derrière une frontière <Suspense> avec
 *      un repli squelette (RouteFallback / <Fallback />), jamais un spinner nu ;
 *   3. le routeur lui-même n'importe JAMAIS statiquement une lib lourde
 *      (leaflet, pdfjs, recharts) ni un composant qui en dépend (MapView,
 *      PdfCanvas, ui/charts) — elles ne doivent vivre que dans les chunks de
 *      pages lazy, hors du bundle initial.
 *
 * Tout sert de garde anti-régression : si une route future est ajoutée en
 * import statique (donc dans le bundle initial) ou en oubliant son <Suspense>,
 * ces assertions échouent.
 *
 * ARC48/ARC54 — Depuis la migration des routes legacy (stock/sav/crm/ventes/
 * installations/reporting/admin/parametres) vers `features/<module>/
 * module.config.jsx` (cf. router/moduleRoutes.jsx), la MAJORITÉ des imports
 * lazy de pages vit désormais dans les configs de module, pas ici — le compte
 * dans `index.jsx` seul n'est donc plus un indicateur fiable de densité de
 * code-splitting (chaque config de module porte sa propre garde implicite via
 * `buildModuleRoutes`, qui enveloppe systématiquement dans `WithLayout`/
 * `<Suspense>`). Le seuil ci-dessous garde seulement l'invariant réel : au
 * moins un import lazy subsiste dans index.jsx (routes non-modulaires : auth/
 * erreurs/publiques + les quelques routes à `errorElement` dédié non
 * exprimables par le registre) — la garde forte contre un import STATIQUE de
 * page reste la deuxième assertion ci-dessous, inchangée.
 */

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(here, 'index.jsx'), 'utf8')

describe('router code-splitting contract (O165)', () => {
  it('charge tous les composants de page via React.lazy(() => import(...))', () => {
    // Au moins un import dynamique lazy. Depuis ARC48/ARC54, la plupart des
    // pages sont enregistrées via features/<module>/module.config.jsx (cf.
    // commentaire de tête) — le vrai garde-fou anti-régression est la seconde
    // assertion ci-dessous (aucun import STATIQUE de page dans index.jsx).
    const lazyImports = source.match(/lazy\(\s*\(\)\s*=>\s*import\(/g) || []
    expect(lazyImports.length).toBeGreaterThan(0)

    // Aucun import statique d'une page : tout le dossier ../pages doit passer
    // par un import() dynamique pour rester découpé par route.
    const staticPageImport = /import\s+[^\n]*\bfrom\s+['"]\.\.\/pages\//.test(source)
    expect(staticPageImport).toBe(false)
  })

  it('enveloppe chaque route dans une frontière Suspense à repli squelette', () => {
    // Le repli partagé est le squelette RouteFallback, pas un spinner nu.
    expect(source).toContain("import RouteFallback from '../components/RouteFallback'")
    expect(source).toContain('const Fallback = () => <RouteFallback />')

    // Chaque ouverture <Suspense ...> du routeur porte le repli squelette : on
    // compte les balises d'ouverture et on exige autant d'occurrences de
    // `fallback={<Fallback />}`. (Une regex `[^>]*>` se ferait piéger par le
    // `/>` de `<Fallback />` — on compare donc deux décomptes indépendants.)
    const suspenseOpens = source.match(/<Suspense\b/g) || []
    const skeletonFallbacks = source.match(/<Suspense fallback=\{<Fallback \/>\}/g) || []
    expect(suspenseOpens.length).toBeGreaterThan(0)
    expect(skeletonFallbacks.length).toBe(suspenseOpens.length)

    // WithLayout (chokepoint des écrans authentifiés) monte un Suspense.
    // VX134(c) — le contenu de route est enveloppé d'un `.route-fade` (fondu au
    // changement de route) À L'INTÉRIEUR du Suspense ; l'invariant reste : la
    // frontière Suspense à repli squelette enveloppe le contenu de route.
    expect(source).toMatch(/<Suspense fallback=\{<Fallback \/>\}>[\s\S]*?<div key=\{pathname\} className="route-fade">\{children\}<\/div>[\s\S]*?<\/Suspense>/)
  })

  it('ne tire aucune lib lourde dans le bundle initial du routeur', () => {
    // Aucun import statique d'une lib lourde ni d'un composant qui en dépend :
    // elles ne doivent être atteintes que via les chunks de pages lazy.
    const forbidden = [
      /from\s+['"]leaflet['"]/,
      /from\s+['"]pdfjs-dist['"]/,
      /from\s+['"]recharts['"]/,
      /from\s+['"][^'"]*\/MapView['"]/,
      /from\s+['"][^'"]*\/PdfCanvas['"]/,
      /from\s+['"][^'"]*\/ui\/charts['"]/,
    ]
    for (const re of forbidden) {
      expect(re.test(source)).toBe(false)
    }
  })
})
