// NTCRM11 — Plan de compte screen: fill and save a complete plan in one session.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))
vi.mock('../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../../api/axios'
import PlanComptePage from './PlanComptePage'

describe('PlanComptePage (NTCRM11)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue({ data: { results: [] } })
  })

  it('creates a new plan de compte with objectives and SWOT in one session', async () => {
    api.post.mockResolvedValueOnce({ data: { id: 3 } })
    api.get
      .mockResolvedValueOnce({ data: { results: [] } })
      .mockResolvedValueOnce({
        data: {
          id: 3, objectifs_strategiques: 'Grandir', revues: [],
          swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
        },
      })

    render(<PlanComptePage clientId={11} />)
    await screen.findByTestId('plan-compte-screen')

    await userEvent.type(
      screen.getByPlaceholderText('Objectifs stratégiques'), 'Grandir')
    await userEvent.click(
      screen.getByRole('button', { name: /Enregistrer le plan de compte/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/crm/plans-compte/',
      expect.objectContaining({ client: 11, objectifs_strategiques: 'Grandir' }),
    ))
  })

  it('shows the reviews timeline when the plan already has revues', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        id: 5, objectifs_strategiques: '', revues: [
          { id: 1, date_revue: '2026-07-01', decisions: 'Relancer' },
        ],
        swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
      },
    })
    render(<PlanComptePage clientId={11} planId={5} />)
    expect(await screen.findByText('Relancer')).toBeInTheDocument()
  })

  // PACT105 — la lecture (`plan.revues`) existait déjà ; AUCUN formulaire
  // n'écrivait sur `/crm/revues-compte/` avant ce lot : l'historique restait
  // vide tant que rien n'était créé.
  describe('PACT105 — création d’une revue de compte', () => {
    const planSansRevue = {
      id: 5, objectifs_strategiques: '', revues: [],
      swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
    }

    it('affiche un état vide explicite tant qu’aucune revue n’existe', async () => {
      api.get.mockResolvedValueOnce({ data: planSansRevue })
      render(<PlanComptePage clientId={11} planId={5} />)
      expect(await screen.findByText('Aucune revue enregistrée.')).toBeInTheDocument()
    })

    it('crée une revue puis elle apparaît dans la liste déjà affichée', async () => {
      api.get
        .mockResolvedValueOnce({ data: planSansRevue })
        .mockResolvedValueOnce({
          data: {
            ...planSansRevue,
            revues: [{ id: 9, date_revue: '2026-02-01', decisions: 'Relancer par WhatsApp' }],
          },
        })
      api.post.mockResolvedValueOnce({ data: { id: 9 } })

      render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findByText('Aucune revue enregistrée.')

      fireEvent.change(screen.getByLabelText('Date de la revue'), { target: { value: '2026-02-01' } })
      await userEvent.type(screen.getByLabelText('Décisions de la revue'), 'Relancer par WhatsApp')
      await userEvent.click(screen.getByRole('button', { name: 'Ajouter une revue' }))

      await waitFor(() => expect(api.post).toHaveBeenCalledWith(
        '/crm/revues-compte/',
        expect.objectContaining({ plan: 5, date_revue: '2026-02-01', decisions: 'Relancer par WhatsApp' }),
      ))
      expect(await screen.findByText('Relancer par WhatsApp')).toBeInTheDocument()
    })
  })
})
