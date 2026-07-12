import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// AlertDialog (Radix) peut sonder matchMedia — même filet que
// ClientRgpdActions.test.jsx (autre écran utilisant AlertDialog).
function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

/* ODX5 — Onglet « Applications » : catalogue de modules (ODX3) admin-gated,
   toggle par module, confirmation de désactivation en cascade, motif
   (`raison`) affiché sous un module désactivé. */

const CATALOGUE = [
  {
    key: 'stock', label: 'Stock', icone: 'package', depends: [],
    installable: true, description: 'Gestion des stocks.', categorie: 'Stock', actif: true,
  },
  {
    key: 'sav', label: 'Après-vente', icone: 'wrench', depends: ['stock'],
    installable: true, description: '', categorie: 'Services', actif: true,
  },
  {
    key: 'flotte', label: 'Flotte', icone: 'truck', depends: [],
    installable: true, description: '', categorie: 'Stock', actif: false,
  },
]

const TOGGLES = [
  { id: 10, module: 'flotte', actif: false, raison: 'Hors offre pilote' },
]

const { catalogue, activer, desactiver, listToggles } = vi.hoisted(() => ({
  catalogue: vi.fn(),
  activer: vi.fn(() => Promise.resolve({ data: { actives: [] } })),
  desactiver: vi.fn(),
  listToggles: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/coreApi', () => ({
  default: {
    modules: {
      catalogue, activer, desactiver,
      toggles: { list: listToggles },
    },
  },
}))

import ApplicationsSection from './ApplicationsSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderWithRole(role) {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(<Provider store={store}><ApplicationsSection /></Provider>)
}

describe('ApplicationsSection (ODX5)', () => {
  it('un rôle non-admin voit un accès restreint (admin-gated, plus strict que responsable)', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    renderWithRole('responsable')
    expect(await screen.findByText('Accès restreint')).toBeInTheDocument()
    expect(catalogue).not.toHaveBeenCalled()
  })

  it('un admin voit le catalogue groupé par catégorie, avec état et motif', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    renderWithRole('admin')

    // « Stock » désigne à la fois le titre de la catégorie et le libellé du
    // module — on scope la recherche à la ligne du module (data-testid) pour
    // ne pas être ambigu vis-à-vis du titre de groupe (même texte).
    const stockRow = await screen.findByTestId('module-row-stock')
    expect(within(stockRow).getByText('Stock')).toBeInTheDocument()
    expect(screen.getByText('Après-vente')).toBeInTheDocument()
    expect(screen.getByText('Flotte')).toBeInTheDocument()
    // Catégories du manifest rendues comme titres de groupe.
    expect(screen.getByText('Services')).toBeInTheDocument()
    // Dépendance affichée en clair (libellé résolu, pas la clé technique).
    expect(screen.getByText(/Dépend de : Stock/)).toBeInTheDocument()
    // Motif de désactivation affiché sous le module désactivé.
    expect(screen.getByText(/Motif : Hors offre pilote/)).toBeInTheDocument()
    // États rendus.
    expect(screen.getAllByText('Activé').length).toBe(2)
    expect(screen.getByText('Désactivé')).toBeInTheDocument()
  })

  it('active un module désactivé (interrupteur → activer)', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('Flotte')

    await user.click(screen.getByRole('switch', { name: 'Activer le module Flotte' }))

    await waitFor(() => expect(activer).toHaveBeenCalledWith('flotte'))
  })

  it('désactive un module sans dépendant actif directement', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    desactiver.mockResolvedValueOnce({ data: { desactives: ['sav'] } })
    const user = userEvent.setup()
    renderWithRole('admin')
    await screen.findByText('Après-vente')

    await user.click(screen.getByRole('switch', { name: 'Désactiver le module Après-vente' }))

    await waitFor(() => expect(desactiver).toHaveBeenCalledWith('sav', { cascade: false }))
  })

  it('propose la cascade sur 400 dépendance, puis désactive en cascade après confirmation', async () => {
    catalogue.mockResolvedValue({ data: CATALOGUE })
    listToggles.mockResolvedValue({ data: TOGGLES })
    desactiver
      .mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            detail: "Impossible de désactiver « stock » : les modules actifs suivants en dépendent — sav.",
            dependants: ['sav'],
          },
        },
      })
      .mockResolvedValueOnce({ data: { desactives: ['stock', 'sav'] } })
    const user = userEvent.setup()
    renderWithRole('admin')
    // « Stock » est ambigu (titre de catégorie + libellé de module) : on
    // attend la ligne du module Stock via son data-testid.
    await screen.findByTestId('module-row-stock')

    await user.click(screen.getByRole('switch', { name: 'Désactiver le module Stock' }))

    // La 400 de dépendance est affichée (dialogue de confirmation cascade).
    expect(await screen.findByText('Désactiver « Stock » ?')).toBeInTheDocument()
    expect(screen.getByText(/les modules actifs suivants en dépendent — sav/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Désactiver en cascade' }))

    await waitFor(() => expect(desactiver).toHaveBeenNthCalledWith(2, 'stock', { cascade: true }))
  })
})
