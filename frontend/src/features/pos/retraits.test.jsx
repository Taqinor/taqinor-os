import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XPOS15 — smoke de la file click-and-collect (API mockée). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { createRetrait, ajouterLigneRetrait } = vi.hoisted(() => ({
  createRetrait: vi.fn(() => Promise.resolve({ data: { id: 9, reference: 'RET-0009' } })),
  ajouterLigneRetrait: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/posApi', () => ({
  default: {
    getRetraits: () => Promise.resolve({
      data: { results: [
        { id: 1, reference: 'RET-0001', statut: 'a_preparer', client_nom: 'Client A', lignes: [{ id: 1 }] },
        { id: 2, reference: 'RET-0002', statut: 'pret', client_nom: 'Client B', lignes: [] },
      ] },
    }),
    marquerPret: () => Promise.resolve({ data: {} }),
    remettreRetrait: () => Promise.resolve({ data: {} }),
    getProduits: () => Promise.resolve({
      data: { results: [{ id: 55, nom: 'Onduleur Deye 6kW', is_archived: false }] },
    }),
    searchClients: (q) => Promise.resolve({
      data: { results: q ? [{ id: 3, nom: 'Client Retrait' }] : [] },
    }),
    createRetrait: (...args) => createRetrait(...args),
    ajouterLigneRetrait: (...args) => ajouterLigneRetrait(...args),
  },
}))

import RetraitsScreen from './RetraitsScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('rendu smoke de RetraitsScreen', () => {
  it('affiche la file et les actions par statut', async () => {
    withProviders(<RetraitsScreen />)
    expect(screen.getByRole('heading', { name: /Retraits en magasin/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('retraits-liste')).toBeInTheDocument())
    expect(screen.getByText('RET-0001')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Marquer prêt/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Remettre/ })).toBeInTheDocument()
  })
})

// WIR151 — `CommandeRetraitViewSet.perform_create`/`ajouter_ligne` étaient
// complets côté backend, sans aucun appelant client (posApi n'exposait ni
// `createRetrait` ni `ajouterLigneRetrait`, l'écran ne faisait que lister).
describe('RetraitsScreen — création d’une commande retrait (WIR151)', () => {
  it('crée une commande retrait avec un client et une ligne', async () => {
    const user = userEvent.setup()
    withProviders(<RetraitsScreen />)
    await waitFor(() => expect(screen.getByTestId('retraits-liste')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Nouvelle commande/ }))
    expect(await screen.findByText('Nouvelle commande retrait')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Client'))
    await user.type(screen.getByPlaceholderText('Nom du client…'), 'Client Retrait')
    await user.click(await screen.findByText('Client Retrait'))

    await user.type(screen.getByLabelText('Ajouter un article'), 'Onduleur')
    await user.click(await screen.findByText('Onduleur Deye 6kW'))

    const submit = screen.getByRole('button', { name: /Créer la commande/ })
    await waitFor(() => expect(submit).toBeEnabled())
    await user.click(submit)

    await waitFor(() => expect(createRetrait).toHaveBeenCalledWith(
      expect.objectContaining({ client: 3 }),
    ))
    await waitFor(() => expect(ajouterLigneRetrait).toHaveBeenCalledWith(
      9, expect.objectContaining({ produit: 55, quantite: 1 }),
    ))
  })
})
