import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT17 — e-signature d'état des lieux + accusé de lecture de la charte
   véhicule. On vérifie que la signature d'un état des lieux appelle
   `etatsDesLieux.signer` et que l'accusé de lecture appelle
   `accusesCharte.create`, sans réseau (client API mocké). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const signer = vi.fn(() => Promise.resolve({ data: {} }))
const accuserCreate = vi.fn(() => Promise.resolve({ data: {} }))
const empty = () => Promise.resolve({ data: [] })

const etatsList = () => Promise.resolve({
  data: [{
    id: 5, vehicule_label: '12345-A-6', moment_display: 'Départ',
    date_constat: '2026-07-01', kilometrage: 1000, etat_general_display: 'Bon',
    nb_photos: 2, signature_conducteur: '', signature_responsable: '',
  }],
})

vi.mock('../../api/flotteApi', () => ({
  default: {
    conducteurs: { list: () => Promise.resolve({ data: [{ id: 1, nom: 'Karim' }] }) },
    vehicules: { list: empty },
    affectations: { list: empty },
    reservations: { list: empty },
    etatsDesLieux: { list: etatsList, signer: (...args) => signer(...args) },
    chartesVehicule: { list: () => Promise.resolve({ data: [{ id: 1, version: 2, date_publication: '2026-06-01' }] }) },
    accusesCharte: { list: empty, create: (...args) => accuserCreate(...args) },
  },
}))

import ConducteursScreen from './ConducteursScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(<ThemeProvider>{ui}</ThemeProvider>)
}

describe('ConducteursScreen — États des lieux (XFLT17 e-signature)', () => {
  it('signe un état des lieux (rôle conducteur) et appelle etatsDesLieux.signer', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'États des lieux' }))
    await waitFor(() => expect(screen.getByText('12345-A-6')).toBeInTheDocument())

    // Les 2 premières actions de ligne s'affichent comme icônes directes
    // (RowActions — max 2 « quick actions » avant le menu kebab).
    await user.click(screen.getByRole('button', { name: 'Signer (conducteur)' }))

    await user.type(screen.getByLabelText('Nom (e-signature)'), 'Karim')
    await user.click(screen.getByRole('button', { name: 'Signer' }))

    await waitFor(() => expect(signer).toHaveBeenCalledWith(5, { role: 'conducteur', nom: 'Karim' }))
  })
})

describe('ConducteursScreen — Charte véhicule (XFLT17 accusé de lecture)', () => {
  it('affiche la version en vigueur et permet d’accuser lecture', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'Charte véhicule' }))
    await waitFor(() => expect(screen.getByText(/version 2/)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Accuser lecture' }))
    await waitFor(() => expect(accuserCreate).toHaveBeenCalledWith({ conducteur: 1 }))
  })
})
