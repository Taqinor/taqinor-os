import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR147 — CRUD du patrimoine (Site/Bâtiment/Niveau/Local) depuis
   `PatrimoineTree.jsx`, jusqu'ici lecture seule. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const createSite = vi.fn(() => Promise.resolve({ data: { id: 99, nom: 'Site B' } }))
const updateSite = vi.fn(() => Promise.resolve({ data: { id: 1, nom: 'Site A modifié' } }))

vi.mock('../../api/immobilierApi', () => ({
  default: {
    sites: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 1, nom: 'Site A', adresse: '', ville: '' }],
      })),
      create: (...args) => createSite(...args),
      update: (...args) => updateSite(...args),
    },
    batiments: { list: vi.fn(() => Promise.resolve({ data: [] })), create: vi.fn(), update: vi.fn() },
    niveaux: { list: vi.fn(() => Promise.resolve({ data: [] })), create: vi.fn(), update: vi.fn() },
    locaux: { list: vi.fn(() => Promise.resolve({ data: [] })), create: vi.fn(), update: vi.fn() },
  },
}))

import PatrimoineTree from './PatrimoineTree'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PatrimoineTree (WIR147)', () => {
  it('crée un site depuis le formulaire « Ajouter un site »', async () => {
    const user = userEvent.setup()
    withProviders(<PatrimoineTree />)
    await waitFor(() => expect(screen.getByText('Site A')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /Ajouter un site/ }))
    await user.type(screen.getByLabelText('Nom'), 'Site B')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createSite).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Site B' }),
    ))
  })

  it('modifie un site existant via « Modifier »', async () => {
    const user = userEvent.setup()
    withProviders(<PatrimoineTree />)
    await waitFor(() => expect(screen.getByText('Site A')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Modifier' }))
    const champNom = screen.getByLabelText('Nom')
    await user.clear(champNom)
    await user.type(champNom, 'Site A modifié')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(updateSite).toHaveBeenCalledWith(
      1, expect.objectContaining({ nom: 'Site A modifié' }),
    ))
  })
})
