import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import ConventionsScreen from './ConventionsScreen'

/* WIR142 — smoke test : liste les conventions et leurs lignes de grille
   tarifaire. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/santeApi', () => ({
  default: {
    conventions: {
      list: () => Promise.resolve({
        data: [{ id: 1, nom: 'CNOPS Casablanca', type: 'cnops', type_display: 'CNOPS', taux_tiers_payant_pct: '80.00', actif: true }],
      }),
      create: () => Promise.resolve({ data: {} }),
    },
    grillesTarifaires: {
      list: () => Promise.resolve({
        data: [{ id: 1, convention: 1, acte: 1, tarif_convention_ttc: '150.00', taux_prise_charge_pct: '80.00' }],
      }),
      create: () => Promise.resolve({ data: {} }),
    },
    actesMedicaux: {
      list: () => Promise.resolve({ data: [{ id: 1, libelle: 'Consultation générale' }] }),
    },
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ConventionsScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ConventionsScreen', () => {
  it('affiche les conventions et la grille tarifaire', async () => {
    renderScreen()

    await waitFor(() => {
      // DataTable rend SIMULTANÉMENT la ligne bureau et la carte mobile
      // (masquage CSS seul, non évalué en jsdom) -> 2 occurrences.
      expect(screen.getAllByText('CNOPS Casablanca').length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText('Consultation générale').length).toBeGreaterThan(0)
  })
})
