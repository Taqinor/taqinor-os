// AERR121 — accueil mobile « Commercial responsable » (NTMOB26), onglet Équipe :
// une lecture des relances en retard rejetée n'est jamais « aucune relance ».
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { isMobileMock } from '../../../test/mobileMocks'
import '../../../test/utilisateur7Mock'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const { crmApiMock } = vi.hoisted(() => ({ crmApiMock: { getRelances: vi.fn() } }))
vi.mock('../../../api/crmApi', () => ({ default: crmApiMock }))
// L'onglet « Moi » (accueil individuel) n'est pas l'objet de cette suite.
vi.mock('./CommercialHome', async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => <div>Accueil individuel</div>,
}))

import EquipeCommercialeHome from './EquipeCommercialeHome'

beforeEach(() => {
  vi.clearAllMocks()
  isMobileMock.mockReturnValue(true)
})

describe('EquipeCommercialeHome (NTMOB26)', () => {
  it("panne : état d'erreur, pas « Aucune relance en retard »", async () => {
    crmApiMock.getRelances.mockRejectedValue(new Error('Network Error'))
    render(<MemoryRouter><EquipeCommercialeHome /></MemoryRouter>)
    await userEvent.click(screen.getByRole('radio', { name: 'Équipe' }))
    expect(await screen.findByText('Lecture impossible')).toBeTruthy()
    expect(screen.queryByText("Aucune relance en retard dans l'équipe")).toBeNull()
    crmApiMock.getRelances.mockResolvedValue({ data: { results: [] } })
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByText("Aucune relance en retard dans l'équipe")).toBeTruthy()
  })
})
