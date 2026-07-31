import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* WIR99/DC12 — l'écran de profil site est le SEUL endroit où un `SiteProfile`
   peut être créé/édité (le modèle et son endpoint existaient, aucun écran ne
   les utilisait). Ce test verrouille : chargement du profil existant du client
   sélectionné, et rendu du formulaire pré-rempli. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

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
