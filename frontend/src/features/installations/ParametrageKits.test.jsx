import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT61 — Paramétrage des kits d'assemblage : nomenclature, gamme, contrôle
   qualité (FG328, XMFG13/14). L'Atelier ne fait que SÉLECTIONNER un kit
   déjà créé — cet écran crée le kit lui-même. */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getKitsAssemblage: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 12, nom: 'Kit variateur pompage', reference_interne: 'KIT-POMP-01', active: true },
  ] } })),
  createKit: vi.fn(() => Promise.resolve({ data: {} })),
  updateKit: vi.fn(() => Promise.resolve({ data: {} })),
  getKitComposants: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createKitComposant: vi.fn(() => Promise.resolve({ data: {} })),
  updateKitComposant: vi.fn(() => Promise.resolve({ data: {} })),
  deleteKitComposant: vi.fn(() => Promise.resolve({ data: {} })),
  getEtapesAssemblageKit: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createEtapeAssemblageKit: vi.fn(() => Promise.resolve({ data: {} })),
  updateEtapeAssemblageKit: vi.fn(() => Promise.resolve({ data: {} })),
  deleteEtapeAssemblageKit: vi.fn(() => Promise.resolve({ data: {} })),
  getControleQualiteModeles: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createControleQualiteModele: vi.fn(() => Promise.resolve({ data: {} })),
  updateControleQualiteModele: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))
vi.mock('../../api/stockApi', () => ({ default: {
  getProduits: () => Promise.resolve({ data: { count: 1, results: [{ id: 55, nom: 'Variateur VEICHI 5.5kW' }] } }),
} }))

import ParametrageKits from './ParametrageKits'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ParametrageKits (PACT61)', () => {
  it('affiche les kits et leur fiche à onglets', async () => {
    render(<ParametrageKits />)
    expect(await screen.findByTestId('kit-12')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Kit variateur pompage' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Nomenclature' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: "Gamme d'étapes" })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Contrôle qualité' })).toBeInTheDocument()
  })

  it('affiche l\'état vide quand aucun kit n\'existe', async () => {
    inst.getKitsAssemblage.mockResolvedValueOnce({ data: { count: 0, results: [] } })
    render(<ParametrageKits />)
    expect((await screen.findAllByText('Aucun kit')).length).toBeGreaterThan(0)
  })

  it('crée un nouveau kit', async () => {
    const user = userEvent.setup()
    render(<ParametrageKits />)
    await screen.findByTestId('kit-12')
    await user.click(screen.getAllByRole('button', { name: 'Nouveau kit' })[0])
    await user.type(screen.getByLabelText('Nom'), 'Kit onduleur résidentiel')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createKit).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Kit onduleur résidentiel' })))
  })

  it('ajoute une ligne de nomenclature', async () => {
    const user = userEvent.setup()
    render(<ParametrageKits />)
    await screen.findByTestId('kit-12')
    await user.click(screen.getAllByRole('button', { name: /Nouveau composant/ })[0])
    await screen.findByRole('option', { name: 'Variateur VEICHI 5.5kW' })
    await user.selectOptions(screen.getByLabelText('Produit (catalogue, optionnel)'), '55')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createKitComposant).toHaveBeenCalledWith(
      expect.objectContaining({ kit: 12, produit: 55 })))
  })

  it('définit une étape de la gamme', async () => {
    const user = userEvent.setup()
    render(<ParametrageKits />)
    await screen.findByTestId('kit-12')
    await user.click(screen.getByRole('tab', { name: "Gamme d'étapes" }))
    await user.click(screen.getAllByRole('button', { name: /Nouvelle étape/ })[0])
    await user.type(screen.getByLabelText('Libellé'), 'Câblage variateur')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createEtapeAssemblageKit).toHaveBeenCalledWith(
      expect.objectContaining({ kit: 12, libelle: 'Câblage variateur', ordre: 1 })))
  })

  it('configure le modèle de contrôle qualité du kit', async () => {
    const user = userEvent.setup()
    render(<ParametrageKits />)
    await screen.findByTestId('kit-12')
    await user.click(screen.getByRole('tab', { name: 'Contrôle qualité' }))
    expect((await screen.findAllByText('Aucun modèle de contrôle qualité configuré')).length).toBeGreaterThan(0)
    await user.click(screen.getAllByRole('button', { name: /Configurer un modèle de contrôle/ })[0])
    await waitFor(() => expect(inst.createControleQualiteModele).toHaveBeenCalledWith(
      expect.objectContaining({ kit: 12, active: true })))
  })
})
