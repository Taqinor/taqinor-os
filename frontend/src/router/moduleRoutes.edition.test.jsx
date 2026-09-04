/* SOL6 — le glob conditionnel de `moduleRoutes.jsx` reste ALIGNÉ sur le
   registre `src/lib/editions.js`.

   Les motifs négatifs du glob sont forcément écrits EN DUR (`import.meta.glob`
   n'accepte que des littéraux). Rien n'empêcherait donc d'ajouter un vertical
   au registre et d'oublier le motif — le vertical reviendrait alors dans le
   dist solaire, et la garde `scripts/check_dist_edition.mjs` ne rougirait que
   bien plus tard, en CI. Ce test compare les deux listes ICI, sur la gate PR.

   La suite unitaire tourne en édition COMPLÈTE (`vitest.config.js` fixe
   `__EDITION_SOLAIRE__` à `false`) : on vérifie donc aussi que TOUS les
   modules, verticaux inclus, sont bien chargés dans ce mode. */
import { describe, it, expect } from 'vitest'

// `?raw` : la SOURCE du module, lue par Vite lui-même (sous jsdom,
// `import.meta.url` n'est pas une URL `file:` — pas de `readFileSync` ici).
import SOURCE from './moduleRoutes.jsx?raw'
import { EDITION_SOLAR, verticauxParques } from '../lib/editions.js'
import { moduleConfigs } from './moduleRoutes.jsx'

describe('SOL6 — glob d\'édition de moduleRoutes', () => {
  it('un motif négatif existe pour CHAQUE vertical parqué', () => {
    const manquants = verticauxParques(EDITION_SOLAR).filter(
      (v) => !SOURCE.includes(`'!../features/${v}/module.config.jsx'`))
    expect(manquants).toEqual([])
  })

  it("aucun motif négatif ne vise un module qui n'est pas parqué", () => {
    const parques = verticauxParques(EDITION_SOLAR)
    const declares = [...SOURCE.matchAll(
      /'!\.\.\/features\/([a-z_]+)\/module\.config\.jsx'/g)].map((m) => m[1])
    expect(declares.sort()).toEqual([...parques].sort())
  })

  it('la condition est LITTÉRALE (build-time), jamais un filtre à l\'exécution', () => {
    expect(SOURCE).toContain('__EDITION_SOLAIRE__')
  })

  it('en édition complète (mode des tests) les verticaux sont chargés', () => {
    const cles = moduleConfigs.map((c) => c.key)
    for (const vertical of verticauxParques(EDITION_SOLAR)) {
      expect(cles).toContain(vertical)
    }
  })
})
