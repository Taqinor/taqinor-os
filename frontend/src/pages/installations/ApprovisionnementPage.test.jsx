import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR110 — écran de consultation « Approvisionnement avancé » : 6 familles
   d'endpoints FG310-318, un onglet par famille. */

// Radix Tabs peut sonder matchMedia — filet standard du dépôt.
function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const api = vi.hoisted(() => ({
  getSeuilsApprobationBcf: vi.fn(),
  getApprobationsBcf: vi.fn(),
  getCommandesCadre: vi.fn(),
  getAppelsCommande: vi.fn(),
  getContratsPrixFournisseur: vi.fn(),
  getReceptionsNonFacturees: vi.fn(),
}))
vi.mock('../../api/installationsApi', () => ({ default: api }))

import ApprovisionnementPage from './ApprovisionnementPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const resolveAll = () => {
  api.getSeuilsApprobationBcf.mockResolvedValue({ data: [{ id: 1, seuil_responsable: 50000, actif: true, date_modification: '2026-07-01' }] })
  api.getApprobationsBcf.mockResolvedValue({ data: [] })
  api.getCommandesCadre.mockResolvedValue({ data: [{ id: 3, reference: 'CC-202607-0001', intitule: 'Panneaux', fournisseur_nom: 'ACME', statut: 'actif', statut_display: 'Actif', lignes: [{}, {}] }] })
  api.getAppelsCommande.mockResolvedValue({ data: [] })
  api.getContratsPrixFournisseur.mockResolvedValue({ data: [] })
  api.getReceptionsNonFacturees.mockResolvedValue({ data: [] })
}

describe('ApprovisionnementPage (WIR110)', () => {
  it('rend les 6 onglets et charge le premier (seuils)', async () => {
    resolveAll()
    render(<ApprovisionnementPage />)
    expect(screen.getByText('Approvisionnement avancé')).toBeInTheDocument()
    // Les 6 déclencheurs d'onglet sont présents.
    expect(screen.getByRole('tab', { name: 'Seuils BCF' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Contrats-cadre' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Réceptions non facturées' })).toBeInTheDocument()
    // L'onglet par défaut (seuils) charge et affiche sa donnée.
    await waitFor(() => expect(api.getSeuilsApprobationBcf).toHaveBeenCalled())
    expect(await screen.findByText('Seuil Responsable (MAD)')).toBeInTheDocument()
  })

  it('change d\'onglet et charge la famille correspondante', async () => {
    resolveAll()
    const user = userEvent.setup()
    render(<ApprovisionnementPage />)
    await screen.findByText('Seuil Responsable (MAD)')

    await user.click(screen.getByRole('tab', { name: 'Contrats-cadre' }))
    await waitFor(() => expect(api.getCommandesCadre).toHaveBeenCalled())
    expect(await screen.findByText('CC-202607-0001')).toBeInTheDocument()
  })
})
