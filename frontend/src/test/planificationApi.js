import { vi } from 'vitest'

/* Doublure PARTAGÉE de `installationsApi` pour les suites Planification (ENF19) :
   les lectures/écritures du calendrier techniciens + les méthodes propres à la
   suite (`supplementaires`, une liste de noms -> `vi.fn()`). À appeler depuis
   `vi.hoisted` : `const api = await vi.hoisted(async () => (await
   import('…/test/planificationApi')).apiPlanification([...]))`. */
const BASE = [
  'getCalendrierInterventions', 'getMaTournee', 'getPlanDeCharge',
  'getConflitsAffectation', 'getNivellementCharge', 'getPlanningCamionnettes',
  'getInstallations', 'updateIntervention',
]

export function apiPlanification(supplementaires = []) {
  const api = {}
  for (const nom of [...BASE, ...supplementaires]) api[nom] = vi.fn()
  return api
}
