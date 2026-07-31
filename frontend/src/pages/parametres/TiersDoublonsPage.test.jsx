import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR152 — `TiersViewSet.doublons` (ARC20, `selectors.find_duplicates`,
   admin-only, LECTURE SEULE) n'avait aucun consommateur. */

const { doublons } = vi.hoisted(() => ({
  doublons: vi.fn(() => Promise.resolve({
    data: {
      count: 1,
      clusters: [
        {
          cle: 'ice', valeur: '001234567000078',
          tiers: [
            { id: 1, nom: 'SARL Atlas', roles: { client: false, fournisseur: true, partenaire: false, soustraitant: false } },
            { id: 2, nom: 'Atlas Partenaire', roles: { client: false, fournisseur: false, partenaire: true, soustraitant: false } },
          ],
        },
      ],
    },
  })),
}))

vi.mock('../../api/tiersApi', () => ({
  default: { doublons: (...args) => doublons(...args) },
}))

import TiersDoublonsPage from './TiersDoublonsPage'

beforeEach(() => { doublons.mockClear() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('TiersDoublonsPage (WIR152)', () => {
  it('affiche les clusters de doublons (même ICE) avec les deux fiches', async () => {
    withProviders(<TiersDoublonsPage />)
    await waitFor(() => expect(screen.getByTestId('doublons-clusters')).toBeInTheDocument())
    expect(screen.getByText('001234567000078')).toBeInTheDocument()
    expect(screen.getByText('SARL Atlas')).toBeInTheDocument()
    expect(screen.getByText('Atlas Partenaire')).toBeInTheDocument()
    expect(screen.getByText('Fournisseur')).toBeInTheDocument()
    expect(screen.getByText('Partenaire')).toBeInTheDocument()
  })

  it('affiche un état vide quand il n’y a aucun doublon', async () => {
    doublons.mockResolvedValueOnce({ data: { count: 0, clusters: [] } })
    withProviders(<TiersDoublonsPage />)
    expect(await screen.findByText('Aucun doublon détecté pour l’instant.')).toBeInTheDocument()
  })
})
