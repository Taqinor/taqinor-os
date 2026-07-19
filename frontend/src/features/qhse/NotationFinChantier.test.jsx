import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR125 — rendre opérable la notation de fin de chantier (gate advisory). */

const { list, calculer, peutCloturer } = vi.hoisted(() => ({
  list: vi.fn(),
  calculer: vi.fn(() => Promise.resolve({ data: {} })),
  peutCloturer: vi.fn(),
}))
vi.mock('../../api/qhseApi', () => ({
  default: {
    notationsFinChantier: { list, calculer, peutCloturer },
  },
}))

import NotationFinChantier from './NotationFinChantier'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('NotationFinChantier (WIR125)', () => {
  it('liste les notations avec score, verdict et « peut clôturer »', async () => {
    list.mockResolvedValue({ data: [
      { id: 1, chantier_id: 42, score: 85, seuil_passage: 70, verdict: 'passe', verdict_display: 'Passé', peut_cloturer: true, nb_items: 6, date_notation: '2026-07-10' },
    ] })
    render(<NotationFinChantier />)
    const card = await screen.findByTestId('notation-1')
    expect(within(card).getByText('Chantier #42')).toBeInTheDocument()
    expect(within(card).getByText('Passé')).toBeInTheDocument()
    expect(within(card).getByText('Peut clôturer')).toBeInTheDocument()
    expect(within(card).getByText('85')).toBeInTheDocument()
  })

  it('déclenche le calcul du score', async () => {
    list.mockResolvedValue({ data: [
      { id: 1, chantier_id: 42, score: null, verdict: null, peut_cloturer: true, nb_items: 6, date_notation: '2026-07-10' },
    ] })
    const user = userEvent.setup()
    render(<NotationFinChantier />)
    const card = await screen.findByTestId('notation-1')
    await user.click(within(card).getByRole('button', { name: 'Calculer le score' }))
    await waitFor(() => expect(calculer).toHaveBeenCalledWith(1))
  })

  it('vérifie si un chantier peut clôturer (gate advisory)', async () => {
    list.mockResolvedValue({ data: [] })
    peutCloturer.mockResolvedValue({ data: { chantier_id: '7', peut_cloturer: false } })
    const user = userEvent.setup()
    render(<NotationFinChantier />)
    await screen.findByText('Ce chantier peut-il clôturer ?')
    await user.type(screen.getByLabelText('Identifiant du chantier'), '7')
    await user.click(screen.getByRole('button', { name: 'Vérifier' }))
    await waitFor(() => expect(peutCloturer).toHaveBeenCalledWith({ chantier_id: '7' }))
    expect(await screen.findByText('Clôture déconseillée')).toBeInTheDocument()
  })
})
