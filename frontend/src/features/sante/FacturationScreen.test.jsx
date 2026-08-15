import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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

const mocks = vi.hoisted(() => ({
  statistiques: vi.fn(() => Promise.resolve({
    data: {
      par_acte: [{ acte_id: 1, acte__libelle: 'Consultation', volume: 5, chiffre_affaires: '1500.00' }],
      par_convention: [{ convention_id: 1, convention__nom: 'CNOPS', nb_factures: 3, ca_tiers_payant: '900.00', ca_total: '1200.00' }],
    },
  })),
}))

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
      // WIR273 — NTSAN28 : bloc « Statistiques » interrogé au montage.
      statistiques: mocks.statistiques,
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

describe('FacturationScreen — statistiques actes/conventions (NTSAN28 / WIR273)', () => {
  it('affiche les deux tableaux (actes les plus facturés + répartition par convention) sans filtre', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.statistiques).toHaveBeenCalledWith({}))
    expect(await screen.findByText('Consultation')).toBeInTheDocument()
    expect(screen.getByText('CNOPS')).toBeInTheDocument()
  })

  it('transmet date_debut/date_fin au serveur quand la période est renseignée', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.statistiques).toHaveBeenCalledWith({}))
    mocks.statistiques.mockClear()

    fireEvent.change(screen.getByLabelText('Date de début des statistiques'), { target: { value: '2026-07-01' } })
    fireEvent.change(screen.getByLabelText('Date de fin des statistiques'), { target: { value: '2026-07-31' } })

    await waitFor(() => expect(mocks.statistiques).toHaveBeenCalledWith({
      date_debut: '2026-07-01', date_fin: '2026-07-31',
    }))
  })
})
