/* Doubles PARTAGÉS de la navigation de l'écran ToitureDesign (modes devis/lead).

   L2 — la confirmation « le calepinage diverge du devis » passe par le provider
   racine, absent du harnais : on répond OUI d'office, le flux PV21
   (resynchroniser puis livrer) reste le comportement testé. `useNavigate` est
   un espion `navigateMock`. */
import { vi } from 'vitest'

vi.mock('../providers/confirm-context', () => ({
  useConfirm: () => () => Promise.resolve(true),
}))
export const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})
