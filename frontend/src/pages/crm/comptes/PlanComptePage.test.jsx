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
      screen.getAllByRole('button', { name: /Enregistrer le plan de compte/i })[0])

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
    expect((await screen.findAllByText('Relancer')).length).toBeGreaterThan(0)
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
      expect((await screen.findAllByText('Aucune revue enregistrée.')).length).toBeGreaterThan(0)
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
      await screen.findAllByText('Aucune revue enregistrée.')

      fireEvent.change(screen.getByLabelText('Date de la revue'), { target: { value: '2026-02-01' } })
      await userEvent.type(screen.getByLabelText('Décisions de la revue'), 'Relancer par WhatsApp')
      await userEvent.click(screen.getAllByRole('button', { name: 'Ajouter une revue' })[0])

      await waitFor(() => expect(api.post).toHaveBeenCalledWith(
        '/crm/revues-compte/',
        expect.objectContaining({ plan: 5, date_revue: '2026-02-01', decisions: 'Relancer par WhatsApp' }),
      ))
      expect((await screen.findAllByText('Relancer par WhatsApp')).length).toBeGreaterThan(0)
    })
  })

  // WIR218 — chaînes vides envoyées au serveur (400 systématique).
  describe('WIR218 — pas de chaîne vide envoyée au serveur', () => {
    it('omet potentiel_estime/prochaine_revue quand vides (jamais une chaîne vide)', async () => {
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
        screen.getAllByRole('button', { name: /Enregistrer le plan de compte/i })[0])

      await waitFor(() => expect(api.post).toHaveBeenCalled())
      const payload = api.post.mock.calls[0][1]
      expect(Object.values(payload)).not.toContain('')
      expect(payload.potentiel_estime).toBeUndefined()
      expect(payload.prochaine_revue).toBeUndefined()
    })

    it('omet prochaine_action_date quand vide dans la création de revue', async () => {
      const planSansRevue = {
        id: 5, objectifs_strategiques: '', revues: [],
        swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
      }
      api.get.mockResolvedValueOnce({ data: planSansRevue })
      api.post.mockResolvedValueOnce({ data: { id: 9 } })

      render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findAllByText('Aucune revue enregistrée.')

      fireEvent.change(screen.getByLabelText('Date de la revue'), { target: { value: '2026-02-01' } })
      await userEvent.click(screen.getAllByRole('button', { name: 'Ajouter une revue' })[0])

      await waitFor(() => expect(api.post).toHaveBeenCalled())
      const payload = api.post.mock.calls[0][1]
      expect(payload.prochaine_action_date).toBeUndefined()
      expect(Object.values(payload)).not.toContain('')
    })
  })

  // WIR218 — section « Activité » du plan de compte (chatter générique).
  describe('WIR218 — section Activité', () => {
    const plan = {
      id: 5, objectifs_strategiques: '', revues: [],
      swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
    }

    it('affiche la timeline chatter du plan de compte', async () => {
      api.get
        .mockResolvedValueOnce({ data: plan })
        .mockResolvedValueOnce({
          data: [
            {
              id: 1, kind: 'modification', field_label: 'Statut', old_value: 'brouillon',
              new_value: 'actif', created_at: '2026-02-01T10:00:00Z', user_nom: 'A',
            },
          ],
        })

      render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findByText('Activité')
      expect((await screen.findAllByText(/actif/)).length).toBeGreaterThan(0)
    })

    it("affiche un état vide tant qu'aucune activité n'existe", async () => {
      api.get
        .mockResolvedValueOnce({ data: plan })
        .mockResolvedValueOnce({ data: [] })

      render(<PlanComptePage clientId={11} planId={5} />)
      expect((await screen.findAllByText('Aucune activité pour le moment.')).length).toBeGreaterThan(0)
    })
  })
})
