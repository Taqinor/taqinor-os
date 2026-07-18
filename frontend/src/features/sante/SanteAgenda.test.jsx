import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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

const annuler = vi.fn(() => Promise.resolve({ data: { penalite_applicable: false } }))

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
            statut: 'planifie',
          },
        ],
      }),
      update: () => Promise.resolve({ data: {} }),
      annuler: (...args) => annuler(...args),
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
  beforeEach(() => {
    window.confirm = vi.fn(() => true)
  })

  it('affiche une colonne par praticien avec ses rendez-vous', async () => {
    renderAgenda()

    await waitFor(() => {
      expect(screen.getByText('Dr. Alami')).toBeInTheDocument()
    })
    expect(screen.getByText('Jean Dupont')).toBeInTheDocument()
    expect(screen.getByTestId('agenda-colonne-1')).toBeInTheDocument()
    expect(screen.getByTestId('rdv-10')).toBeInTheDocument()
  })

  it('WIR53 — annule un rendez-vous depuis l’agenda (délai/pénalité calculés serveur)', async () => {
    renderAgenda()

    await waitFor(() => {
      expect(screen.getByText('Jean Dupont')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Annuler ce rendez-vous/i }))

    await waitFor(() => {
      expect(annuler).toHaveBeenCalledWith(10, 'clinique')
    })
  })
})
