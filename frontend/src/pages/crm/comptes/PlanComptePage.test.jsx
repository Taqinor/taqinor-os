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
      // WIR218 a ajouté un 2ᵉ GET au montage (`…/historique/`) : les mocks
      // en cascade `mockResolvedValueOnce` ne peuvent plus décrire la
      // séquence. On mocke par URL — le rechargement d'après-POST voit alors
      // vraiment la revue créée côté serveur.
      let planCourant = planSansRevue
      api.get.mockImplementation((url) => {
        if (url === '/crm/plans-compte/5/historique/') return Promise.resolve({ data: [] })
        if (url === '/crm/plans-compte/5/') return Promise.resolve({ data: planCourant })
        return Promise.resolve({ data: { results: [] } })
      })
      api.post.mockImplementationOnce(() => {
        planCourant = {
          ...planSansRevue,
          revues: [{ id: 9, date_revue: '2026-02-01', decisions: 'Relancer par WhatsApp' }],
        }
        return Promise.resolve({ data: { id: 9 } })
      })

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

  // WIR218 — `prochaine_revue`/`potentiel_estime`/`prochaine_action_date`
  // (DateField/DecimalField nullables) partaient systématiquement en chaîne
  // vide → 400 DRF garanti. Convention ClientPrixContractuelsTab : un champ
  // nullable vide est OMIS du payload (undefined), jamais envoyé en `''`.
  describe('WIR218 — champs nullables vides omis du payload', () => {
    const planMinimal = {
      id: 5, objectifs_strategiques: 'Grandir', potentiel_estime: '', prochaine_revue: '',
      revues: [], swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
    }

    it('le PATCH du plan ne contient pas potentiel_estime/prochaine_revue en chaîne vide', async () => {
      api.get.mockResolvedValueOnce({ data: planMinimal })
      api.patch.mockResolvedValueOnce({ data: { id: 5 } })

      render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findByTestId('plan-compte-screen')

      await userEvent.click(screen.getAllByRole('button', { name: /Enregistrer le plan de compte/i })[0])

      await waitFor(() => expect(api.patch).toHaveBeenCalled())
      const [, payload] = api.patch.mock.calls[0]
      expect(payload.potentiel_estime).toBeUndefined()
      expect(payload.prochaine_revue).toBeUndefined()
    })

    it('le POST de la revue n’envoie pas prochaine_action_date si non renseigné', async () => {
      api.get.mockResolvedValueOnce({ data: planMinimal })
      api.post.mockResolvedValueOnce({ data: { id: 9 } })

      render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findByTestId('plan-compte-screen')

      fireEvent.change(screen.getByLabelText('Date de la revue'), { target: { value: '2026-02-01' } })
      await userEvent.click(screen.getAllByRole('button', { name: 'Ajouter une revue' })[0])

      await waitFor(() => expect(api.post).toHaveBeenCalledWith('/crm/revues-compte/', expect.anything()))
      const [, payload] = api.post.mock.calls.find((c) => c[0] === '/crm/revues-compte/')
      expect(payload.prochaine_action_date).toBeUndefined()
    })

    it('lie réellement le champ « Date de la prochaine action » : envoyé quand renseigné', async () => {
      api.get.mockResolvedValueOnce({ data: planMinimal })
      api.post.mockResolvedValueOnce({ data: { id: 9 } })

      render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findByTestId('plan-compte-screen')

      fireEvent.change(screen.getByLabelText('Date de la revue'), { target: { value: '2026-02-01' } })
      fireEvent.change(screen.getByLabelText('Date de la prochaine action'), { target: { value: '2026-03-15' } })
      await userEvent.click(screen.getAllByRole('button', { name: 'Ajouter une revue' })[0])

      await waitFor(() => expect(api.post).toHaveBeenCalledWith(
        '/crm/revues-compte/',
        expect.objectContaining({ prochaine_action_date: '2026-03-15' }),
      ))
    })
  })

  // WIR218 — section « Activité » (GET plans-compte/<id>/historique/, montée
  // via ChatterTimeline comme PolitiqueStockDetailPage) : jusqu'ici invisible.
  describe('WIR218 — section Activité', () => {
    it('charge et affiche l’historique du plan (changement de statut)', async () => {
      const planActif = {
        id: 5, objectifs_strategiques: '', statut: 'actif', revues: [],
        swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
      }
      api.get
        .mockResolvedValueOnce({ data: planActif })
        .mockResolvedValueOnce({
          data: [{
            id: 1, kind: 'modification', field_label: 'Statut',
            old_value: 'brouillon', new_value: 'actif',
            user_username: 'sami', created_at: '2026-08-01T10:00:00Z',
          }],
        })

      const { container } = render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findByTestId('plan-compte-screen')

      expect((await screen.findAllByText(/Statut/)).length).toBeGreaterThan(0)
      await waitFor(() => {
        const texte = container.querySelector('.chatter-modification')?.textContent || ''
        expect(texte).toContain('actif')
      })
    })

    it('appelle bien /crm/plans-compte/<id>/historique/', async () => {
      api.get
        .mockResolvedValueOnce({
          data: {
            id: 5, objectifs_strategiques: '', revues: [],
            swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
          },
        })
        .mockResolvedValueOnce({ data: [] })

      render(<PlanComptePage clientId={11} planId={5} />)
      await screen.findByTestId('plan-compte-screen')

      await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/plans-compte/5/historique/'))
    })
  })
})
