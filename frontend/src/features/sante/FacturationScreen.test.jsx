import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import FacturationScreen from './FacturationScreen'

/* WIR142 — smoke test : liste les factures santé avec leur montant dû
   (toujours calculé côté serveur) et propose un formulaire d'encaissement. */

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
    facturesSante: {
      list: () => Promise.resolve({
        data: [
          {
            id: 1, patient: 1, total_ttc: '150.00', part_patient_ttc: '30.00',
            montant_du: '30.00', statut: 'emise', statut_display: 'Émise',
            date_emission: '2026-07-01T09:00:00Z',
          },
        ],
      }),
      create: () => Promise.resolve({ data: {} }),
    },
    admissions: {
      list: () => Promise.resolve({ data: [{ id: 1, patient: 1 }] }),
    },
    actesRealises: {
      list: () => Promise.resolve({ data: [] }),
    },
    patients: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Alami', prenom: 'Sara' }] }),
    },
    paiementsSante: {
      list: () => Promise.resolve({ data: [] }),
      create: () => Promise.resolve({ data: {} }),
    },
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <FacturationScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('FacturationScreen', () => {
  it('affiche les factures avec leur montant dû et le formulaire d\'encaissement', async () => {
    renderScreen()

    await waitFor(() => {
      expect(screen.getByText('Émise')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /Encaisser/i })).toBeInTheDocument()
  })
})
