import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* FG280 — alarmes onduleur : liste + acquitter + escalader. savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    getAlarmes: vi.fn(),
    acquitterAlarme: vi.fn(),
    escaladerAlarme: vi.fn(),
  },
}))

// WIR31 — création manuelle d'une alarme : POST /sav/alarmes-onduleur/ (api
// axios direct, hors savApi — cf. creerAlarme dans SavAlarmesPage.jsx).
vi.mock('../../api/axios', () => ({
  default: { post: vi.fn(() => Promise.resolve({ data: {} })) },
}))

import savApi from '../../api/savApi'
import api from '../../api/axios'
import SavAlarmesPage from './SavAlarmesPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SavAlarmesPage', () => {
  it('affiche une alarme active avec les boutons acquitter/escalader', async () => {
    savApi.getAlarmes.mockResolvedValue({
      data: [{
        id: 1, code: 'E07', gravite: 'critique', gravite_display: 'Critique',
        statut: 'active', statut_display: 'Active',
        equipement_produit: 'Onduleur Huawei', equipement_serie: 'SN-1',
        date_detection: '2026-07-01T10:00:00Z',
      }],
    })
    render(<SavAlarmesPage />)
    expect(await screen.findByText('E07')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Acquitter' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Escalader/ })).toBeInTheDocument()
  })

  it('acquitte une alarme', async () => {
    savApi.getAlarmes.mockResolvedValue({
      data: [{
        id: 2, code: 'F12', gravite: 'warning', gravite_display: 'Avertissement',
        statut: 'active', statut_display: 'Active',
      }],
    })
    savApi.acquitterAlarme.mockResolvedValue({ data: {} })
    render(<SavAlarmesPage />)
    await screen.findByText('F12')
    fireEvent.click(screen.getByRole('button', { name: 'Acquitter' }))
    await waitFor(() => expect(savApi.acquitterAlarme).toHaveBeenCalledWith(2))
  })

  it('affiche un état vide quand aucune alarme', async () => {
    savApi.getAlarmes.mockResolvedValue({ data: [] })
    render(<SavAlarmesPage />)
    expect(await screen.findByText('Aucune alarme')).toBeInTheDocument()
  })

  describe('WIR31 — formulaire « Créer une alarme »', () => {
    it('ouvre le formulaire de création et crée une alarme via POST', async () => {
      savApi.getAlarmes.mockResolvedValue({ data: [] })
      render(<SavAlarmesPage />)
      await screen.findByText('Aucune alarme')

      fireEvent.click(screen.getByRole('button', { name: /Créer une alarme/ }))
      fireEvent.change(screen.getByPlaceholderText('ex. E07'), { target: { value: 'E07' } })
      fireEvent.change(screen.getByPlaceholderText('ex. Défaut isolement'),
        { target: { value: 'Défaut isolement' } })
      fireEvent.click(screen.getByRole('button', { name: 'Créer' }))

      await waitFor(() => expect(api.post).toHaveBeenCalledWith('/sav/alarmes-onduleur/',
        expect.objectContaining({ code: 'E07', gravite: 'warning', libelle: 'Défaut isolement' })))
    })

    it('désactive le bouton Créer tant que le code est vide', async () => {
      savApi.getAlarmes.mockResolvedValue({ data: [] })
      render(<SavAlarmesPage />)
      await screen.findByText('Aucune alarme')
      fireEvent.click(screen.getByRole('button', { name: /Créer une alarme/ }))
      expect(screen.getByRole('button', { name: 'Créer' })).toBeDisabled()
    })
  })
})
