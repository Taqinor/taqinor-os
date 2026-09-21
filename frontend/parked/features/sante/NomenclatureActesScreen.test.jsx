import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import NomenclatureActesScreen from './NomenclatureActesScreen'

/* NTSAN7 — smoke test : liste les actes, affiche leur statut (actif/désactivé)
   sans jamais proposer de suppression physique (soft-disable uniquement).
   Appels API mockés (hors réseau). */

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
    actesMedicaux: {
      list: () => Promise.resolve({
        data: [
          {
            id: 1, libelle: 'Consultation générale', code_ngap: '',
            cotation_lettre_cle: '', tarif_base_ttc: '150.00', actif: true,
          },
        ],
      }),
      create: () => Promise.resolve({ data: {} }),
      desactiver: () => Promise.resolve({ data: {} }),
      activer: () => Promise.resolve({ data: {} }),
    },
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <NomenclatureActesScreen />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('NomenclatureActesScreen', () => {
  it('affiche les actes existants avec leur statut et une action de bascule', async () => {
    renderScreen()

    await waitFor(() => {
      expect(screen.getByText('Consultation générale')).toBeInTheDocument()
    })
    expect(screen.getByText('Actif')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Désactiver/i })).toBeInTheDocument()
  })
})
