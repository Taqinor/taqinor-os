import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import AdmissionsScreen from './AdmissionsScreen'

/* WIR142 — smoke test : liste les admissions et propose la clôture des
   admissions non clôturées (jamais de mutation directe du statut). */

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
    admissions: {
      list: () => Promise.resolve({
        data: [
          {
            id: 1, patient: 1, praticien: 1, type: 'consultation',
            type_display: 'Consultation', statut: 'en_cours',
            statut_display: 'En cours', date_admission: '2026-07-01T09:00:00Z',
          },
        ],
      }),
      create: () => Promise.resolve({ data: {} }),
      cloturer: () => Promise.resolve({ data: {} }),
    },
    patients: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Alami', prenom: 'Sara' }] }),
    },
    praticiens: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Dr Bennani' }] }),
    },
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <AdmissionsScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AdmissionsScreen', () => {
  it('affiche les admissions existantes avec une action de clôture', async () => {
    renderScreen()

    await waitFor(() => {
      expect(screen.getByText('Alami Sara')).toBeInTheDocument()
    })
    expect(screen.getByText('En cours')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Clôturer/i })).toBeInTheDocument()
  })
})
