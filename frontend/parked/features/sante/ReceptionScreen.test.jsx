import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import ReceptionScreen from './ReceptionScreen'

/* NTSAN18 — smoke test de l'écran Réception : le planning du jour se charge,
   et le bouton « Patient arrivé » déclenche le check-in serveur (statut
   `arrive`, salle d'attente). Appels API mockés (hors réseau). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const checkin = vi.fn(() => Promise.resolve({ data: {} }))
const annuler = vi.fn(() => Promise.resolve({ data: { penalite_applicable: false } }))

vi.mock('../../api/santeApi', () => ({
  default: {
    praticiens: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Dr. Alami' }] }),
    },
    patients: {
      list: () => Promise.resolve({ data: [] }),
      create: () => Promise.resolve({ data: { id: 9, nom: 'Nouveau' } }),
    },
    rendezvous: {
      list: () => Promise.resolve({
        data: [
          {
            id: 20, praticien: 1, patient: 5, patient_nom: 'Fatima Zahra',
            date_heure_debut: '2026-08-03T09:00:00Z', duree_min: 30,
            statut: 'planifie', statut_display: 'Planifié',
          },
        ],
      }),
      create: () => Promise.resolve({ data: {} }),
      checkin: (...args) => checkin(...args),
      annuler: (...args) => annuler(...args),
    },
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <ReceptionScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ReceptionScreen', () => {
  it("affiche le planning du jour et permet le check-in en salle d'attente", async () => {
    renderScreen()

    await waitFor(() => {
      expect(screen.getByText('Fatima Zahra')).toBeInTheDocument()
    })

    const bouton = screen.getByRole('button', { name: /Patient arrivé/i })
    fireEvent.click(bouton)

    await waitFor(() => {
      expect(checkin).toHaveBeenCalledWith(20)
    })
  })

  it('WIR53 — annule un rendez-vous depuis la réception', async () => {
    window.confirm = vi.fn(() => true)
    renderScreen()

    await waitFor(() => {
      expect(screen.getByText('Fatima Zahra')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Annuler ce rendez-vous/i }))

    await waitFor(() => {
      expect(annuler).toHaveBeenCalledWith(20, 'patient')
    })
  })
})
