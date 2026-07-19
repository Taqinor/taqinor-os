// LW26 — la palette ⌘K fusionne les actions contextuelles d'un LeadWorkspace
// ouvert (« Fiche ouverte », posées/retirées via `taqinor:lead-workspace-actions`,
// cf. features/crm/workspace/LeadWorkspace.jsx) dans sa propre liste, EN
// PREMIER, filtrables comme les autres — jamais présentes une fois la fiche
// fermée.
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

// Monte le composant SANS l'ouvrir — le listener `taqinor:lead-workspace-actions`
// est posé au montage (indépendant de `open`), donc les actions contextuelles
// doivent pouvoir arriver AVANT même que l'utilisateur appuie sur ⌘K (une
// fiche peut s'ouvrir bien avant que la palette ne le soit).
function mountPalette() {
  return render(<CommandPalette />, { wrapper: MemoryRouter })
}

function openPaletteEvent() {
  act(() => { window.dispatchEvent(new Event('taqinor:command-palette')) })
}

function postLeadActions(actions) {
  act(() => {
    window.dispatchEvent(new CustomEvent('taqinor:lead-workspace-actions', { detail: { actions } }))
  })
}

const SAMPLE_ACTIONS = [
  { id: 'lw-archive', label: 'Archiver le lead', run: vi.fn() },
  { id: 'lw-convert', label: 'Convertir en client', run: vi.fn() },
  { id: 'lw-goto-toiture', label: 'Aller à : Toiture & site', run: vi.fn() },
]

describe('CommandPalette — actions contextuelles « Fiche ouverte » (LW26)', () => {
  it('fiche fermée (aucun événement reçu) : la section « Fiche ouverte » est absente', () => {
    mountPalette()
    openPaletteEvent()
    expect(screen.queryByText('Fiche ouverte')).toBeNull()
  })

  it('fiche ouverte : liste les actions contextuelles, section EN PREMIER', () => {
    mountPalette()
    postLeadActions(SAMPLE_ACTIONS)
    openPaletteEvent()
    expect(screen.getByText('Fiche ouverte')).toBeInTheDocument()
    expect(screen.getByText('Archiver le lead')).toBeInTheDocument()
    expect(screen.getByText('Convertir en client')).toBeInTheDocument()
    expect(screen.getByText('Aller à : Toiture & site')).toBeInTheDocument()
    const groupTitles = [...document.querySelectorAll('.cmdk-group-title')].map((el) => el.textContent)
    expect(groupTitles[0]).toBe('Fiche ouverte')
  })

  it('sélectionner une action contextuelle exécute son callback (jamais une navigation)', () => {
    mountPalette()
    postLeadActions(SAMPLE_ACTIONS)
    openPaletteEvent()
    fireEvent.click(screen.getByText('Archiver le lead'))
    expect(SAMPLE_ACTIONS[0].run).toHaveBeenCalledTimes(1)
    expect(navigateMock).not.toHaveBeenCalled()
    expect(openQuickCreateMock).not.toHaveBeenCalled()
  })

  it('la frappe filtre les actions contextuelles par libellé (comme Actions/Créer)', () => {
    mountPalette()
    postLeadActions(SAMPLE_ACTIONS)
    openPaletteEvent()
    fireEvent.change(screen.getByPlaceholderText('Rechercher ou lancer une action…'), { target: { value: 'toiture' } })
    expect(screen.getByText('Aller à : Toiture & site')).toBeInTheDocument()
    expect(screen.queryByText('Archiver le lead')).toBeNull()
  })

  it('la fiche se ferme (actions: []) : la section « Fiche ouverte » disparaît de la palette déjà ouverte', () => {
    mountPalette()
    postLeadActions(SAMPLE_ACTIONS)
    openPaletteEvent()
    expect(screen.getByText('Fiche ouverte')).toBeInTheDocument()
    postLeadActions([])
    expect(screen.queryByText('Fiche ouverte')).toBeNull()
  })
})
