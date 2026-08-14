import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// NTDMO16 — bloc « Visites guidées » des Paramètres : liste les 6 tours avec
// leur statut vu/non-vu + un bouton « Revoir » par tour qui les remet à zéro.
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import api from '../../api/axios'
import { VisitesGuideesBlock } from './OnboardingSection'

const TOURS = [
  { tour_key: 'devis', vu: true },
  { tour_key: 'leads', vu: false },
]

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => cleanup())

describe('VisitesGuideesBlock (NTDMO16)', () => {
  it('affiche le statut vu/non-vu de chaque tour', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    render(<VisitesGuideesBlock />)
    expect(await screen.findByText('Créer un devis')).toBeInTheDocument()
    expect(screen.getByText('Déjà vue')).toBeInTheDocument()
    expect(screen.getByText('Pas encore vue')).toBeInTheDocument()
  })

  it('cliquer « Revoir » sur un tour déjà vu appelle revoir/ et rafraîchit', async () => {
    api.get.mockResolvedValueOnce({ data: TOURS })
    api.post.mockResolvedValueOnce({
      data: [{ tour_key: 'devis', vu: false }, { tour_key: 'leads', vu: false }],
    })
    api.get.mockResolvedValueOnce({
      data: [{ tour_key: 'devis', vu: false }, { tour_key: 'leads', vu: false }],
    })
    render(<VisitesGuideesBlock />)
    await screen.findByText('Créer un devis')
    const rows = screen.getAllByRole('button', { name: /Revoir/ })
    await userEvent.click(rows[0])
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/onboarding/tours/devis/revoir/'))
    await waitFor(() => expect(screen.getAllByText('Pas encore vue')).toHaveLength(2))
  })
})
