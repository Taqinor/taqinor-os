import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import FacturationScreen from './FacturationScreen'

/* WIR142 — smoke test : liste les factures santé avec leur montant dû
   (toujours calculé côté serveur) et propose un formulaire d'encaissement.
   WIR273 (NTSAN28) — bloc « Statistiques » : `statistiques_actes_et_conventions`
   était déjà câblé côté backend (actes les plus facturés + répartition du CA
   par convention) mais AUCUN écran ne l'appelait. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { statistiques } = vi.hoisted(() => ({
  statistiques: vi.fn(() => Promise.resolve({
    data: {
      par_acte: [{ acte_id: 1, acte__libelle: 'Consultation', volume: 12, chiffre_affaires: '3600.00' }],
      par_convention: [
        { convention_id: 2, convention__nom: 'CNOPS', ca_tiers_payant: '2400.00', ca_total: '3000.00', nb_factures: 8 },
      ],
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
      statistiques,
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

beforeEach(() => {
  statistiques.mockClear()
})

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

  // WIR273 (NTSAN28) — deux tableaux (actes les plus facturés + répartition
  // du CA par convention), chargés SANS filtre au montage.
  it('WIR273 — charge et rend les deux tableaux de statistiques sans filtre au montage', async () => {
    renderScreen()

    await waitFor(() => expect(statistiques).toHaveBeenCalledWith({}))
    expect(await screen.findByText('Actes les plus facturés')).toBeInTheDocument()
    expect(screen.getByText('Consultation')).toBeInTheDocument()
    expect(screen.getByText('Répartition du CA par convention')).toBeInTheDocument()
    expect(screen.getByText('CNOPS')).toBeInTheDocument()
  })

  // WIR273 — les dates choisies sont bien transmises au wrapper, seulement
  // celles renseignées (jamais une chaîne vide envoyée pour l'autre).
  it('WIR273 — transmet les dates choisies au filtre des statistiques', async () => {
    renderScreen()
    await waitFor(() => expect(statistiques).toHaveBeenCalledWith({}))

    fireEvent.change(screen.getByLabelText('Date de début (statistiques)'), {
      target: { value: '2026-01-01' },
    })
    fireEvent.change(screen.getByLabelText('Date de fin (statistiques)'), {
      target: { value: '2026-06-30' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Filtrer' }))

    await waitFor(() => expect(statistiques).toHaveBeenLastCalledWith({
      date_debut: '2026-01-01', date_fin: '2026-06-30',
    }))
  })

  it('WIR273 — ne transmet que la date renseignée (l’autre reste absente du filtre)', async () => {
    renderScreen()
    await waitFor(() => expect(statistiques).toHaveBeenCalledWith({}))

    fireEvent.change(screen.getByLabelText('Date de début (statistiques)'), {
      target: { value: '2026-01-01' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Filtrer' }))

    await waitFor(() => expect(statistiques).toHaveBeenLastCalledWith({ date_debut: '2026-01-01' }))
    expect(statistiques.mock.calls.at(-1)[0]).not.toHaveProperty('date_fin')
  })
})
