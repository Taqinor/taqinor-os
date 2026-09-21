import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import migrationApi from '../../api/migrationApi'
import PartenairesCertifiesPage from './PartenairesCertifiesPage'

vi.mock('../../api/migrationApi', () => ({
  default: {
    listPartenairesCertifies: vi.fn(),
  },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function withProviders(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

const LIGNE = {
  id: 1,
  nom: 'Intégrateur Atlas',
  type_partenaire: 'installateur',
  zone: 'Casablanca',
  niveau_certification: 'certifie',
  niveau_certification_display: 'Certifié',
  specialites: ['compta', 'crm'],
  date_certification: '2026-01-10',
  date_expiration_certification: '2027-01-10',
  certification_expiree: false,
  nb_deploiements_reussis: 3,
  score: 62,
  historique_deploiements: [
    { client_final: 'Coopérative Souss', statut: 'reussi', date_go_live: '2026-04-10', note_satisfaction: 9 },
  ],
}

describe('PartenairesCertifiesPage (NTMIG29)', () => {
  it('affiche les partenaires certifiés avec niveau, spécialités et score', async () => {
    migrationApi.listPartenairesCertifies.mockResolvedValue({ data: [LIGNE] })
    withProviders(<PartenairesCertifiesPage />)

    expect((await screen.findAllByText('Intégrateur Atlas'))[0]).toBeTruthy()
    expect(screen.getAllByText('Certifié').length).toBeGreaterThan(0)
    expect(screen.getAllByText('compta, crm').length).toBeGreaterThan(0)
  })

  it('refiltre avec niveau/spécialité choisis', async () => {
    migrationApi.listPartenairesCertifies.mockResolvedValue({ data: [LIGNE] })
    const user = userEvent.setup()
    withProviders(<PartenairesCertifiesPage />)
    await screen.findAllByText('Intégrateur Atlas')

    await user.selectOptions(
      screen.getByLabelText(/Niveau de certification minimum/i), 'certifie')
    await user.selectOptions(
      screen.getByLabelText(/^Spécialité$/i), 'compta')

    await waitFor(() => {
      expect(migrationApi.listPartenairesCertifies).toHaveBeenLastCalledWith(
        { niveau_min: 'certifie', specialite: 'compta' })
    })
  })

  it('affiche un état vide quand aucun partenaire ne correspond', async () => {
    migrationApi.listPartenairesCertifies.mockResolvedValue({ data: [] })
    withProviders(<PartenairesCertifiesPage />)
    expect((await screen.findAllByText(/Aucun partenaire qualifié/i))[0]).toBeTruthy()
  })

  it('affiche une erreur de chargement au lieu de planter', async () => {
    migrationApi.listPartenairesCertifies.mockRejectedValue({
      response: { data: { detail: 'Accès refusé.' } },
    })
    withProviders(<PartenairesCertifiesPage />)
    expect(await screen.findByText(/Accès refusé\./)).toBeTruthy()
  })
})
