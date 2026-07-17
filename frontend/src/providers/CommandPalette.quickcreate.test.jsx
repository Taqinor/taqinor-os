// NTUX10 — CommandPalette : la section « Créer » fusionne le quick-create
// MODAL (Lead/Client/Ticket SAV/Produit) avec la nav restante (Devis, écran
// dédié) ; sélectionner une entrée modal ouvre le quick-create SANS naviguer.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('../lib/search/entityRoutes', () => ({
  ROUTE: {}, TYPE_LABEL: {}, TYPE_ACCENT: {},
  useEntitySearch: () => ({ groups: [], loading: false, failed: false }),
}))

const openQuickCreateMock = vi.fn()
vi.mock('../features/uxviews/quickcreate/quickCreateEvents', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, openQuickCreate: (...a) => openQuickCreateMock(...a) }
})

import { CommandPalette } from './CommandPalette'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function openPalette() {
  render(<CommandPalette />, { wrapper: MemoryRouter })
  act(() => { window.dispatchEvent(new Event('taqinor:command-palette')) })
}

describe('CommandPalette — quick-create (NTUX10)', () => {
  it('la section Créer liste Devis (nav) + Lead/Client/Ticket SAV/Produit (modal)', () => {
    openPalette()
    expect(screen.getByText('Créer un devis')).toBeInTheDocument()
    expect(screen.getByText('Créer un lead')).toBeInTheDocument()
    expect(screen.getByText('Créer un client')).toBeInTheDocument()
    expect(screen.getByText('Créer un ticket SAV')).toBeInTheDocument()
    expect(screen.getByText('Créer un produit')).toBeInTheDocument()
    // Une seule occurrence de chaque libellé — pas de doublon nav+modal.
    expect(screen.getAllByText('Créer un lead')).toHaveLength(1)
  })

  it('sélectionner « Créer un lead » ouvre le quick-create SANS naviguer', () => {
    openPalette()
    fireEvent.click(screen.getByText('Créer un lead'))
    expect(openQuickCreateMock).toHaveBeenCalledWith('lead')
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('sélectionner « Créer un devis » navigue toujours (écran dédié, pas de modal)', () => {
    openPalette()
    fireEvent.click(screen.getByText('Créer un devis'))
    expect(navigateMock).toHaveBeenCalledWith('/ventes/devis/nouveau')
    expect(openQuickCreateMock).not.toHaveBeenCalled()
  })

  it('sélectionner « Créer un ticket SAV » ouvre le quick-create ticket', () => {
    openPalette()
    fireEvent.click(screen.getByText('Créer un ticket SAV'))
    expect(openQuickCreateMock).toHaveBeenCalledWith('ticket')
  })
})
