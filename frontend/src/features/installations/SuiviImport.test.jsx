import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT56 — Import et douane : dossiers, frais, coût débarqué (FG315/FG316). */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getDossiersImport: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 12, reference: 'IMP-202608-0001', designation: 'Conteneur panneaux Q3', statut_douane: 'commande', statut_douane_display: 'Commandé' },
  ] } })),
  createDossierImport: vi.fn(() => Promise.resolve({ data: {} })),
  avancerDossierImport: vi.fn(() => Promise.resolve({ data: {} })),
  getLandedCostDossier: vi.fn(() => Promise.resolve({ data: {
    dossier_id: 12, total_fob: 100000, total_frais: 8000, total_landed: 108000,
    lignes: [{ ligne_id: 55, produit_id: null, designation: 'Panneau 550W', quantite: 100, valeur_fob: 100000, quote_part_frais: 8000, cout_debarque_total: 108000, cout_debarque_unitaire: 1080 }],
  } })),
  appliquerCoutStockDossier: vi.fn(() => Promise.resolve({ data: {} })),
  getFraisImport: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createFraisImport: vi.fn(() => Promise.resolve({ data: {} })),
  deleteFraisImport: vi.fn(() => Promise.resolve({ data: {} })),
  getLandedCostLignes: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createLandedCostLigne: vi.fn(() => Promise.resolve({ data: {} })),
  deleteLandedCostLigne: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))

import SuiviImport from './SuiviImport'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SuiviImport (PACT56)', () => {
  it('charge les dossiers et affiche la fiche sélectionnée', async () => {
    render(<SuiviImport />)
    expect((await screen.findAllByText('Conteneur panneaux Q3')).length).toBeGreaterThan(0)
    expect(await screen.findByRole('heading', { name: 'Conteneur panneaux Q3' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Frais' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Coût débarqué' })).toBeInTheDocument()
  })

  it('affiche l\'état vide quand aucun dossier n\'existe', async () => {
    inst.getDossiersImport.mockResolvedValueOnce({ data: { count: 0, results: [] } })
    render(<SuiviImport />)
    expect((await screen.findAllByText("Aucun dossier d'import")).length).toBeGreaterThan(0)
  })

  it('crée un dossier d\'import', async () => {
    const user = userEvent.setup()
    render(<SuiviImport />)
    await screen.findAllByText('Conteneur panneaux Q3')
    await user.click(screen.getAllByRole('button', { name: /Nouveau dossier/ })[0])
    await user.type(screen.getByLabelText('Désignation'), 'Conteneur onduleurs')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createDossierImport).toHaveBeenCalledWith(
      expect.objectContaining({ designation: 'Conteneur onduleurs' })))
  })

  it('fait avancer le statut douanier', async () => {
    const user = userEvent.setup()
    render(<SuiviImport />)
    await screen.findAllByText('Conteneur panneaux Q3')
    await user.click(screen.getAllByRole('button', { name: 'Faire avancer' })[0])
    await waitFor(() => expect(inst.avancerDossierImport).toHaveBeenCalledWith(12))
  })

  it('saisit un frais depuis l\'onglet Frais', async () => {
    const user = userEvent.setup()
    render(<SuiviImport />)
    await screen.findAllByText('Conteneur panneaux Q3')
    await user.click(screen.getAllByRole('button', { name: /Nouveau frais/ })[0])
    await user.type(screen.getByLabelText('Montant (MAD)'), '8000')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createFraisImport).toHaveBeenCalledWith(
      expect.objectContaining({ dossier: 12, montant: '8000' })))
  })

  it('calcule le coût débarqué par SKU depuis l\'onglet dédié', async () => {
    inst.getLandedCostLignes.mockResolvedValue({ data: { count: 1, results: [
      { id: 55, designation: 'Panneau 550W', quantite: 100, valeur_fob: 100000 },
    ] } })
    const user = userEvent.setup()
    render(<SuiviImport />)
    await screen.findAllByText('Conteneur panneaux Q3')
    await user.click(screen.getByRole('tab', { name: 'Coût débarqué' }))
    expect(await screen.findByTestId('landed-ligne-55')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Calculer le coût débarqué' })[0])
    await waitFor(() => expect(inst.getLandedCostDossier).toHaveBeenCalledWith(12))
    expect(await screen.findByTestId('landed-totaux')).toHaveTextContent('108')
    expect(within(screen.getByTestId('landed-ligne-55')).getByText(/Débarqué/)).toBeInTheDocument()
  })
})
