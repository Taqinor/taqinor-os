import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR147 — écran Locataires (CRUD + résolution client ventes), jusqu'ici
   sans aucun écran alors que `LocataireViewSet` existe côté backend. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const createLocataire = vi.fn(() => Promise.resolve({ data: { id: 5, nom: 'Ali Ben' } }))
const resolveClient = vi.fn(() => Promise.resolve({ data: { client_ventes_id: 42 } }))

vi.mock('../../api/immobilierApi', () => ({
  default: {
    locataires: {
      list: vi.fn(() => Promise.resolve({
        data: [
          {
            id: 1, nom: 'Fatima Z', type_locataire: 'particulier',
            type_locataire_display: 'Particulier', telephone: '0600000000',
            email: 'fz@example.com', client_ventes_id: null,
          },
        ],
      })),
      create: (...args) => createLocataire(...args),
      update: vi.fn(),
      resolveClient: (...args) => resolveClient(...args),
    },
  },
}))

import LocatairesPage from './LocatairesPage'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('LocatairesPage (WIR147)', () => {
  it('liste les locataires existants', async () => {
    withProviders(<LocatairesPage />)
    await waitFor(() => expect(screen.getByText('Fatima Z')).toBeInTheDocument())
    expect(screen.getByText('Non résolu')).toBeInTheDocument()
  })

  it('crée un locataire depuis le formulaire', async () => {
    const user = userEvent.setup()
    withProviders(<LocatairesPage />)
    await waitFor(() => expect(screen.getByText('Fatima Z')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Ajouter un locataire' }))
    await user.type(screen.getByLabelText('Nom / raison sociale'), 'Ali Ben')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createLocataire).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Ali Ben' }),
    ))
  })

  it('résout le client ventes d\'un locataire non résolu', async () => {
    const user = userEvent.setup()
    withProviders(<LocatairesPage />)
    await waitFor(() => expect(screen.getByText('Fatima Z')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Résoudre client' }))
    await waitFor(() => expect(resolveClient).toHaveBeenCalledWith(1))
  })
})
