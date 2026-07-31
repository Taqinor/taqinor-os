import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR152 — `TiersViewSet` (ARC17, CRUD complet) n'était consommé qu'en
   resolver de nom par deux écrans compta — aucun écran répertoire. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { tiersCreate, tiersUpdate } = vi.hoisted(() => ({
  tiersCreate: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
  tiersUpdate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/tiersApi', () => ({
  default: {
    tiers: {
      list: () => Promise.resolve({
        data: [
          {
            id: 1, type_tiers: 'entreprise', type_tiers_display: 'Entreprise',
            nom: 'SARL Atlas', nom_complet: 'SARL Atlas', telephone: '0600000000',
            email: 'contact@atlas.ma', ville: 'Casablanca',
            is_client: true, is_fournisseur: false, is_partenaire: false, is_soustraitant: false,
          },
        ],
      }),
      create: (...args) => tiersCreate(...args),
      update: (...args) => tiersUpdate(...args),
    },
  },
}))

import TiersPage from './TiersPage'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('TiersPage (WIR152)', () => {
  it('affiche le répertoire avec le rôle et les coordonnées', async () => {
    withProviders(<TiersPage />)
    await waitFor(() => expect(screen.getAllByText('SARL Atlas').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Client').length).toBeGreaterThan(0)
    expect(screen.getAllByText('contact@atlas.ma').length).toBeGreaterThan(0)
  })

  it('crée un tiers depuis le bouton dédié', async () => {
    const user = userEvent.setup()
    withProviders(<TiersPage />)
    await waitFor(() => expect(screen.getAllByText('SARL Atlas').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouveau tiers/ }))
    await user.type(screen.getByLabelText('Nom / Raison sociale'), 'Ferme Est')
    await user.click(screen.getByRole('button', { name: 'Créer le tiers' }))

    await waitFor(() => expect(tiersCreate).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Ferme Est' }),
    ))
  })

  it('modifie un tiers existant depuis l’action de ligne', async () => {
    const user = userEvent.setup()
    withProviders(<TiersPage />)
    await waitFor(() => expect(screen.getAllByText('SARL Atlas').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Modifier' })[0])
    expect(await screen.findByText('Modifier — SARL Atlas')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(tiersUpdate).toHaveBeenCalledWith(
      1, expect.objectContaining({ nom: 'SARL Atlas' }),
    ))
  })
})
