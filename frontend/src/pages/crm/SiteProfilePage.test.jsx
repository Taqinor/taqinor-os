import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR99/DC12 — l'écran de profil site est le SEUL endroit où un `SiteProfile`
   peut être créé/édité (le modèle et son endpoint existaient, aucun écran ne
   les utilisait). Ce test verrouille : chargement du profil existant du client
   sélectionné, et rendu du formulaire pré-rempli. */

beforeAll(polyfillResizeObserver)

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({
      data: [{ id: 42, nom: 'ACME', prenom: 'SARL' }],
    })),
    getSiteProfiles: vi.fn(() => Promise.resolve({
      data: [{
        id: 7, client: 42,
        facture_hiver: '1200.00', facture_ete: '900.00', ete_differente: true,
        conso_mensuelle_kwh: '850.00', raccordement: 'triphase',
        type_installation: 'agricole', pompe_cv: '7.50',
        pompe_hmt_m: '60.00', pompe_debit_m3h: '12.00',
        type_toiture: 'tole', surface_toiture_m2: '140.00',
        inclinaison_deg: '15.00',
      }],
    })),
    createSiteProfile: vi.fn(),
    updateSiteProfile: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import SiteProfilePage from './SiteProfilePage'
import { polyfillResizeObserver } from '../../test/selectNatif'

describe('SiteProfilePage (WIR99 — création/édition du profil site)', () => {
  it('demande de choisir un client tant qu\'aucun n\'est sélectionné', async () => {
    render(<SiteProfilePage />)
    expect(await screen.findByText(/Sélectionnez un client/)).toBeInTheDocument()
  })

  it('charge la liste des clients au montage', async () => {
    render(<SiteProfilePage />)
    await waitFor(() => expect(crmApi.getClients).toHaveBeenCalled())
    expect(screen.getByText('Profils site')).toBeInTheDocument()
  })
})

describe('SiteProfilePage — AERR116', () => {
  async function choisirClient(user) {
    await waitFor(() => expect(crmApi.getClients).toHaveBeenCalled())
    await user.click(screen.getByRole('combobox'))
    await user.click(await screen.findByText('ACME SARL'))
  }

  it('lecture rejetée : Enregistrer désactivé, aucun doublon', async () => {
    crmApi.getSiteProfiles.mockRejectedValueOnce(new Error('500'))
    const user = userEvent.setup()
    render(<SiteProfilePage />)
    await choisirClient(user)
    expect(await screen.findByTestId('profil-illisible')).toHaveTextContent('Profil illisible')
    expect(screen.getByRole('button', { name: /Créer le profil|Enregistrer le profil/ })).toBeDisabled()
    expect(crmApi.createSiteProfile).not.toHaveBeenCalled()
  })

  it('400 sur un champ : message sous le champ', async () => {
    crmApi.updateSiteProfile.mockRejectedValueOnce({
      response: { status: 400, data: { surface_toiture_m2: ['Surface invalide.'] } },
    })
    const user = userEvent.setup()
    render(<SiteProfilePage />)
    await choisirClient(user)
    await user.click(await screen.findByRole('button', { name: 'Enregistrer le profil' }))
    expect(await screen.findByText('Surface invalide.')).toBeInTheDocument()
    expect(screen.getByLabelText('Surface toiture (m²)')).toHaveAttribute('aria-invalid', 'true')
  })
})
