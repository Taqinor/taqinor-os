import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import SanteAgenda from './SanteAgenda'

/* NTSAN4 — smoke test de l'agenda : une colonne par praticien, un rendez-vous
   affiché dans la colonne de son praticien. Appels API mockés (hors réseau). */

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
    praticiens: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Dr. Alami' }] }),
    },
    rendezvous: {
      list: () => Promise.resolve({
        data: [
          {
            id: 10, praticien: 1, patient: 5, patient_nom: 'Jean Dupont',
            date_heure_debut: '2026-08-03T09:00:00Z', duree_min: 30,
          },
        ],
      }),
      update: () => Promise.resolve({ data: {} }),
    },
  },
}))

function renderAgenda() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <SanteAgenda />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('SanteAgenda', () => {
  it('affiche une colonne par praticien avec ses rendez-vous', async () => {
    renderAgenda()

    await waitFor(() => {
      expect(screen.getByText('Dr. Alami')).toBeInTheDocument()
    })
    expect(screen.getByText('Jean Dupont')).toBeInTheDocument()
    expect(screen.getByTestId('agenda-colonne-1')).toBeInTheDocument()
    expect(screen.getByTestId('rdv-10')).toBeInTheDocument()
  })
})
