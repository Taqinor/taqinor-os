import { vi } from 'vitest'

/* Doublure PARTAGÉE de `installationsApi` pour les suites AteliersPage (ENF19) :
   les lectures de l'atelier + le lien du bon PDF, plus les méthodes propres à la
   suite (`supplementaires`, une liste de noms -> `vi.fn()`). À appeler depuis
   `vi.hoisted` : `const api = await vi.hoisted(async () => (await
   import('…/test/ateliersApi')).apiAteliers([...]))`. */
const LECTURES = [
  'getOrdresAssemblage', 'getOrdresDemontage', 'getKitsAssemblage',
  'getDisponibiliteAssemblage', 'getControleQualiteAssemblage', 'getHistoriqueAssemblage',
  'getEtapesAssemblage', 'getLignesAssemblage', 'getKitStructure',
]

export function apiAteliers(supplementaires = []) {
  const api = { bonAssemblageUrl: (id) => `/api/x/${id}/bon-pdf/` }
  for (const nom of [...LECTURES, ...supplementaires]) api[nom] = vi.fn()
  return api
}
