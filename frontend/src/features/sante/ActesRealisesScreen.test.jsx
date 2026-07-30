import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import ActesRealisesScreen from './ActesRealisesScreen'

/* WIR142 — smoke test : liste les actes réalisés avec le tarif appliqué
   (toujours calculé côté serveur) et leur statut de facturation. */

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
    actesRealises: {
      list: () => Promise.resolve({
        data: [
          {
            id: 1, admission: 1, patient: 1, praticien: 1, acte: 1,
            date_realisation: '2026-07-01T09:00:00Z', quantite: 1,
            tarif_applique_ttc: '150.00', facture_sante: null,
          },
        ],
      }),
      create: () => Promise.resolve({ data: {} }),
    },
    admissions: {
      list: () => Promise.resolve({ data: [{ id: 1, patient: 1 }] }),
    },
    patients: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Alami', prenom: 'Sara' }] }),
    },
    praticiens: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Dr Bennani' }] }),
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
        <ActesRealisesScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ActesRealisesScreen', () => {
  it('affiche les actes réalisés non facturés avec leur tarif appliqué', async () => {
    renderScreen()

    await waitFor(() => {
      expect(screen.getByText('150.00')).toBeInTheDocument()
    })
    expect(screen.getByText('Non facturé')).toBeInTheDocument()
  })
})
