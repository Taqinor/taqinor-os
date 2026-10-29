/* ENF19 — `vi.mock('react-router-dom', …)` commun : le vrai module, avec
   `useNavigate` remplacé par le mock du test. Usage :
   vi.mock('react-router-dom', () => import('<…>/test/routerMock').then(
     (m) => m.routerAvecNavigate(() => mocks.navigate))) */
import { vi } from 'vitest'

export async function routerAvecNavigate(getNavigate) {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => getNavigate() }
}
