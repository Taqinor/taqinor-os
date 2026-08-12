import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT57 — Prix négociés fournisseurs : écriture des commandes-cadres et
   contrats de prix (FG314/FG318), en-têtes + lignes. */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getCommandesCadre: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 3, reference: 'CC-202608-0001', intitule: 'Accord panneaux 2026', fournisseur_nom: 'Solar Import SARL', statut: 'actif', statut_display: 'Actif', lignes: [
      { id: 21, produit_nom: null, designation: 'Panneau 550W', prix_negocie: '1200', volume_engage: '500', volume_consomme: '120', volume_restant: '380' },
    ] },
  ] } })),
  createCommandeCadre: vi.fn(() => Promise.resolve({ data: {} })),
  activerCommandeCadre: vi.fn(() => Promise.resolve({ data: {} })),
  cloturerCommandeCadre: vi.fn(() => Promise.resolve({ data: {} })),
  createCommandeCadreLigne: vi.fn(() => Promise.resolve({ data: {} })),
  getContratsPrixFournisseur: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createContratPrixFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
  activerContratPrixFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
  expirerContratPrixFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
  createContratPrixLigne: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))
vi.mock('../../api/stockApi', () => ({ default: {
  getFournisseurs: () => Promise.resolve({ data: { count: 1, results: [{ id: 8, nom: 'Solar Import SARL' }] } }),
} }))

import PrixNegocies from './PrixNegocies'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PrixNegocies (PACT57)', () => {
  it('affiche les commandes-cadres avec leurs lignes et le volume restant', async () => {
    render(<PrixNegocies />)
    expect(await screen.findByTestId('commande-cadre-3')).toBeInTheDocument()
    expect(within(screen.getByTestId('commande-cadre-3')).getByText(/Volume restant : 380 \/ 500/)).toBeInTheDocument()
  })

  it('crée une commande-cadre avec un fournisseur', async () => {
    const user = userEvent.setup()
    render(<PrixNegocies />)
    await screen.findByTestId('commande-cadre-3')
    await user.click(screen.getAllByRole('button', { name: /Nouvelle commande-cadre/ })[0])
    await screen.findByRole('option', { name: 'Solar Import SARL' })
    await user.type(screen.getByLabelText('Intitulé'), 'Accord onduleurs 2026')
    await user.selectOptions(screen.getByLabelText('Fournisseur'), '8')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createCommandeCadre).toHaveBeenCalledWith(
      expect.objectContaining({ intitule: 'Accord onduleurs 2026', fournisseur: 8 })))
  })

  it('ajoute une ligne de prix négocié à une commande-cadre', async () => {
    const user = userEvent.setup()
    render(<PrixNegocies />)
    const row = await screen.findByTestId('commande-cadre-3')
    await user.click(within(row).getByRole('button', { name: /Ligne/ }))
    await user.type(screen.getByLabelText('Désignation'), 'Onduleur 5kW')
    await user.type(screen.getByLabelText('Prix négocié (MAD)'), '4500')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createCommandeCadreLigne).toHaveBeenCalledWith(
      expect.objectContaining({ commande_cadre: 3, designation: 'Onduleur 5kW', prix_negocie: '4500' })))
  })

  it('crée un contrat de prix depuis l\'onglet dédié', async () => {
    const user = userEvent.setup()
    render(<PrixNegocies />)
    await screen.findByTestId('commande-cadre-3')
    await user.click(screen.getByRole('tab', { name: 'Contrats de prix' }))
    expect((await screen.findAllByText('Aucun contrat de prix')).length).toBeGreaterThan(0)
    await user.click(screen.getAllByRole('button', { name: /Nouveau contrat de prix/ })[0])
    await screen.findByRole('option', { name: 'Solar Import SARL' })
    await user.type(screen.getByLabelText('Intitulé'), 'Prix cadre variateurs')
    await user.selectOptions(screen.getByLabelText('Fournisseur'), '8')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createContratPrixFournisseur).toHaveBeenCalledWith(
      expect.objectContaining({ intitule: 'Prix cadre variateurs', fournisseur: 8 })))
  })
})
