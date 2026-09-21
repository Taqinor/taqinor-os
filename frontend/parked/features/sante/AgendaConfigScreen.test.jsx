import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import AgendaConfigScreen from './AgendaConfigScreen'

/* WIR142 — smoke test : les 4 paramétrages agenda (horaires, indisponibilités,
   motifs, sites) se chargent et s'affichent — tous additifs. */

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
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Dr Bennani' }] }),
    },
    salles: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Salle 1' }] }),
    },
    horairesOuverturePraticien: {
      list: () => Promise.resolve({
        data: [{ id: 1, praticien: 1, jour_semaine_display: 'Lundi', heure_debut: '08:00', heure_fin: '18:00' }],
      }),
      create: () => Promise.resolve({ data: {} }),
    },
    indisponibilitesPraticien: {
      list: () => Promise.resolve({ data: [] }),
      create: () => Promise.resolve({ data: {} }),
    },
    motifsConsultation: {
      list: () => Promise.resolve({ data: [{ id: 1, libelle: 'Suivi post-op', actif: true }] }),
      create: () => Promise.resolve({ data: {} }),
    },
    sitesPraticien: {
      list: () => Promise.resolve({ data: [] }),
      create: () => Promise.resolve({ data: {} }),
    },
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <AgendaConfigScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('AgendaConfigScreen', () => {
  it('affiche les horaires et motifs configurés', async () => {
    renderScreen()

    await waitFor(() => {
      expect(screen.getByText('Suivi post-op')).toBeInTheDocument()
    })
    expect(screen.getByText(/Lundi 08:00–18:00/)).toBeInTheDocument()
  })
})
