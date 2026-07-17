import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTAGR4 — liste des parcelles + démarrage de campagne depuis une parcelle
   libre. Réseau mocké (client API), pas de dépendance à un backend réel. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { campagnesCreate } = vi.hoisted(() => ({
  campagnesCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/agricultureApi', () => ({
  default: {
    parcelles: {
      list: () => Promise.resolve({
        data: [
          {
            id: 1, nom: 'Parcelle Nord', code: 'PN-01', culture_principale: 'Blé',
            superficie_ha: '4.2', statut: 'jachere', statut_display: 'Jachère',
            geometrie_gps: [{ lat: 33.29, lng: -8.53 }],
          },
          {
            id: 2, nom: 'Parcelle Sud', code: 'PS-02', culture_principale: 'Orge',
            superficie_ha: '2.1', statut: 'en_culture', statut_display: 'En culture',
            geometrie_gps: null,
          },
        ],
      }),
    },
    campagnes: { create: (...args) => campagnesCreate(...args) },
  },
}))

import ParcellesPage from './ParcellesPage'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ParcellesPage (NTAGR4)', () => {
  it('affiche la liste des parcelles avec superficie/culture/statut', async () => {
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))
    expect(screen.getAllByText(/4\.2 ha/).length).toBeGreaterThan(0)
  })

  it('démarre une campagne depuis une parcelle libre (jachère)', async () => {
    const user = userEvent.setup()
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Nord').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Démarrer une campagne' })[0])
    await user.type(screen.getByLabelText('Culture'), 'Tomate')
    await user.click(screen.getByRole('button', { name: 'Démarrer la campagne' }))

    await waitFor(() => expect(campagnesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ parcelle: 1, culture: 'Tomate', statut: 'en_cours' }),
    ))
  })

  it('n’offre pas « Démarrer une campagne » pour une parcelle déjà en culture', async () => {
    withProviders(<ParcellesPage />)
    await waitFor(() => expect(screen.getAllByText('Parcelle Sud').length).toBeGreaterThan(0))
    // DataTable rend desktop + mobile (2 occurrences) — seule Parcelle Nord
    // (jachère) propose l'action, jamais Parcelle Sud (déjà en_culture).
    expect(screen.getAllByRole('button', { name: 'Démarrer une campagne' }).length).toBe(2)
  })
})
