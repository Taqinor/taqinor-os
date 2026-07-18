import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
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

const {
  signer, accuserCreate, empty, etatsList, conducteursCreate, getEmployes,
} = vi.hoisted(() => ({
  signer: vi.fn(() => Promise.resolve({ data: {} })),
  accuserCreate: vi.fn(() => Promise.resolve({ data: {} })),
  empty: () => Promise.resolve({ data: [] }),
  etatsList: () => Promise.resolve({
    data: [{
      id: 5, vehicule_label: '12345-A-6', moment_display: 'Départ',
      date_constat: '2026-07-01', kilometrage: 1000, etat_general_display: 'Bon',
      nb_photos: 2, signature_conducteur: '', signature_responsable: '',
    }],
  }),
  conducteursCreate: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
  getEmployes: vi.fn(() => Promise.resolve({
    data: [{ id: 42, nom: 'Alami', prenom: 'Youssef', telephone: '0600000000' }],
  })),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    conducteurs: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Karim' }] }),
      create: (...args) => conducteursCreate(...args),
    },
    vehicules: { list: empty },
    affectations: { list: empty },
    reservations: { list: empty },
    etatsDesLieux: { list: etatsList, signer: (...args) => signer(...args) },
    chartesVehicule: { list: () => Promise.resolve({ data: [{ id: 1, version: 2, date_publication: '2026-06-01' }] }) },
    accusesCharte: { list: empty, create: (...args) => accuserCreate(...args) },
  },
}))

vi.mock('../../api/rhApi', () => ({
  default: {
    getEmployes: (...args) => getEmployes(...args),
  },
}))

import ConducteursScreen from './ConducteursScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ConducteursScreen — États des lieux (XFLT17 e-signature)', () => {
  it('signe un état des lieux (rôle conducteur) et appelle etatsDesLieux.signer', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'États des lieux' }))
    // DataTable rend la table desktop ET les cartes mobiles dans le DOM (le
    // point de rupture est géré en CSS) : deux correspondances attendues.
    await waitFor(() => expect(screen.getAllByText('12345-A-6').length).toBeGreaterThan(0))

    // Les 2 premières actions de ligne s'affichent comme icônes directes
    // (RowActions — max 2 « quick actions » avant le menu kebab). Idem : une
    // occurrence par rendu (desktop + mobile), on prend la première.
    await user.click(screen.getAllByRole('button', { name: 'Signer (conducteur)' })[0])

    await user.type(screen.getByLabelText('Nom (e-signature)'), 'Karim')
    await user.click(screen.getByRole('button', { name: 'Signer' }))

    await waitFor(() => expect(signer).toHaveBeenCalledWith(5, { role: 'conducteur', nom: 'Karim' }))
  })
})

describe('ConducteursScreen — Conducteurs (WIR4 création)', () => {
  it('crée un conducteur lié à un employé RH avec les champs XFLT27', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(await screen.findByRole('button', { name: /Nouveau conducteur/ }))
    await user.selectOptions(screen.getByLabelText('Employé RH (option.)'), '42')

    expect(screen.getByLabelText('Nom complet')).toHaveValue('Alami Youssef')
    expect(screen.getByLabelText('Téléphone')).toHaveValue('0600000000')

    await user.type(screen.getByLabelText('N° carte conducteur pro.'), 'CCP-1')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(conducteursCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        employe_id: 42, nom: 'Alami Youssef',
        carte_conducteur_pro_numero: 'CCP-1',
      }),
    ))
  })
})

describe('ConducteursScreen — Charte véhicule (XFLT17 accusé de lecture)', () => {
  it('affiche la version en vigueur et permet d’accuser lecture', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'Charte véhicule' }))
    await waitFor(() => expect(screen.getByText(/version 2/)).toBeInTheDocument())

    // DataTable rend la table desktop ET les cartes mobiles dans le DOM (le
    // point de rupture est géré en CSS) : deux boutons identiques, on prend
    // le premier.
    await user.click(screen.getAllByRole('button', { name: 'Accuser lecture' })[0])
    await waitFor(() => expect(accuserCreate).toHaveBeenCalledWith({ conducteur: 1 }))
  })
})
