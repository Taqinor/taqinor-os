/* Doubles PARTAGÉS de la navigation de l'écran ToitureDesign (modes devis/lead).

   L2 — la confirmation « le calepinage diverge du devis » passe par le provider
   racine, absent du harnais : on répond OUI d'office, le flux PV21
   (resynchroniser puis livrer) reste le comportement testé. `useNavigate` est
   un espion `navigateMock`. AERR155 — la sortie d'une scène modifiée passe par
   la même boîte : `confirmMock` (OUI par défaut) permet d'y répondre « Rester ». */
import { vi } from 'vitest'

const { confirmMock } = vi.hoisted(() => ({ confirmMock: vi.fn(() => Promise.resolve(true)) }))
export { confirmMock }
vi.mock('../providers/confirm-context', () => ({
  useConfirm: () => confirmMock,
}))
export const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})
