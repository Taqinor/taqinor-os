import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT22 — deux opérations en masse : réaffectation conducteur en masse
   (ConducteursScreen) et duplication (rollout) d'un plan d'entretien sur une
   sélection d'actifs (EntretienScreen). On vérifie l'appel exact au bon
   endpoint flotteApi, sans réseau. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { masse, rollout, empty } = vi.hoisted(() => ({
  masse: vi.fn(() => Promise.resolve({ data: { reussies: [{ vehicule_id: 1, conducteur_id: 2 }], echecs: [] } })),
  rollout: vi.fn(() => Promise.resolve({ data: { crees: [{ id: 9 }], ignores: [] } })),
  empty: () => Promise.resolve({ data: [] }),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    conducteurs: { list: () => Promise.resolve({ data: [{ id: 2, nom: 'Karim' }] }) },
    vehicules: { list: () => Promise.resolve({ data: [{ id: 1, immatriculation: '12345-A-6' }] }) },
    affectations: { list: empty, masse: (...args) => masse(...args) },
    reservations: { list: empty },
    etatsDesLieux: { list: empty },
    chartesVehicule: { list: empty },
    accusesCharte: { list: empty },
    actifs: { list: () => Promise.resolve({ data: [{ id: 5, label: '12345-A-6' }] }) },
    plansEntretien: {
      list: () => Promise.resolve({ data: [{ id: 3, actif_label: '12345-A-6', type_entretien: 'Vidange', actif: true }] }),
      rollout: (...args) => rollout(...args),
    },
    echeancesEntretien: { list: empty },
    garages: { list: empty },
    ordresReparation: { list: empty },
    signalements: { list: empty },
    pneumatiques: { list: empty },
    pieces: { list: empty },
  },
}))

import ConducteursScreen from './ConducteursScreen'
import EntretienScreen from './EntretienScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Reaffectation en masse (XFLT22)', () => {
  it('envoie les lignes vehicule/conducteur + date_debut a affectations.masse', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'Affectations' }))
    await user.click(screen.getByRole('button', { name: 'Réaffectation en masse' }))

    await user.type(screen.getByLabelText('Date de début (toutes les lignes)'), '2026-07-10')
    await user.selectOptions(screen.getByLabelText('Véhicule ligne 1'), '1')
    await user.selectOptions(screen.getByLabelText('Conducteur ligne 1'), '2')
    await user.click(screen.getByRole('button', { name: 'Réaffecter' }))

    await waitFor(() => expect(masse).toHaveBeenCalledWith({
      date_debut: '2026-07-10',
      reaffectations: [{ vehicule_id: 1, conducteur_id: 2 }],
    }))
  })
})

describe('Rollout de plan entretien (XFLT22)', () => {
  it('duplique un plan sur les actifs choisis', async () => {
    const user = userEvent.setup()
    withProviders(<EntretienScreen />)

    // Le bouton « Dupliquer sur… » est une action de ligne de l'onglet Plans
    // (l'onglet par défaut est Échéances).
    await user.click(screen.getByRole('tab', { name: 'Plans' }))
    await waitFor(() => expect(screen.getAllByText('Vidange').length).toBeGreaterThan(0))
    await user.click(screen.getAllByRole('button', { name: 'Dupliquer sur…' })[0])
    await user.click(screen.getByLabelText('Actifs cibles'))
    // Scope au listbox du MultiSelect : la même valeur apparaît aussi dans
    // les rangées de la DataTable en arrière-plan (desktop + mobile).
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByText('12345-A-6'))
    await user.click(screen.getByRole('button', { name: 'Dupliquer' }))

    await waitFor(() => expect(rollout).toHaveBeenCalledWith(3, [5]))
  })
})
