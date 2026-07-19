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
  reservationsCreate, demandesVehiculeCreate, etatsDesLieuxCreate, charteCreate,
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
  reservationsCreate: vi.fn(() => Promise.resolve({ data: { id: 11 } })),
  demandesVehiculeCreate: vi.fn(() => Promise.resolve({ data: { id: 12 } })),
  etatsDesLieuxCreate: vi.fn(() => Promise.resolve({ data: { id: 13 } })),
  charteCreate: vi.fn(() => Promise.resolve({ data: { id: 14, version: 3 } })),
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    conducteurs: {
      list: () => Promise.resolve({ data: [{ id: 1, nom: 'Karim' }] }),
      create: (...args) => conducteursCreate(...args),
    },
    vehicules: { list: () => Promise.resolve({ data: [{ id: 7, immatriculation: '12345-A-6' }] }) },
    affectations: { list: empty },
    reservations: { list: empty, create: (...args) => reservationsCreate(...args) },
    demandesVehicule: { list: empty, create: (...args) => demandesVehiculeCreate(...args) },
    etatsDesLieux: {
      list: etatsList,
      signer: (...args) => signer(...args),
      create: (...args) => etatsDesLieuxCreate(...args),
    },
    chartesVehicule: {
      list: () => Promise.resolve({ data: [{ id: 1, version: 2, date_publication: '2026-06-01' }] }),
      create: (...args) => charteCreate(...args),
    },
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

describe('ConducteursScreen — Réservations (WIR41a création)', () => {
  it('crée une réservation depuis l’onglet Réservations', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'Réservations' }))
    await user.click(await screen.findByRole('button', { name: 'Nouvelle réservation' }))

    await user.selectOptions(screen.getByLabelText('Véhicule'), '7')
    await user.type(screen.getByLabelText('Début'), '2026-08-01T08:00')
    await user.type(screen.getByLabelText('Fin'), '2026-08-01T18:00')
    await user.click(screen.getByRole('button', { name: 'Réserver' }))

    await waitFor(() => expect(reservationsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ vehicule: 7 }),
    ))
  })
})

describe('ConducteursScreen — Demandes de véhicule (WIR41b)', () => {
  it('soumet une demande depuis le nouvel onglet', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'Demandes de véhicule' }))
    await user.click(await screen.findByRole('button', { name: 'Demander un véhicule' }))

    await user.type(screen.getByLabelText('Besoin / objet de la demande'), 'Mission chantier')
    await user.type(screen.getByLabelText('Début souhaité'), '2026-08-01')
    await user.type(screen.getByLabelText('Fin souhaitée'), '2026-08-03')
    await user.click(screen.getByRole('button', { name: 'Demander' }))

    await waitFor(() => expect(demandesVehiculeCreate).toHaveBeenCalledWith(
      expect.objectContaining({ besoin: 'Mission chantier' }),
    ))
  })
})

describe('ConducteursScreen — États des lieux (WIR41c création du constat)', () => {
  it('crée un constat avant toute signature', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'États des lieux' }))
    await user.click(await screen.findByRole('button', { name: 'Nouveau constat' }))

    await user.selectOptions(screen.getByLabelText('Véhicule'), '7')
    await user.type(screen.getByLabelText('Date du constat'), '2026-08-01T09:00')
    await user.click(screen.getByRole('button', { name: 'Créer le constat' }))

    await waitFor(() => expect(etatsDesLieuxCreate).toHaveBeenCalledWith(
      expect.objectContaining({ vehicule: 7, moment: 'depart' }),
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

  it('publie une nouvelle version (WIR44) — accusés repassés « à faire »', async () => {
    const user = userEvent.setup()
    withProviders(<ConducteursScreen />)

    await user.click(screen.getByRole('tab', { name: 'Charte véhicule' }))
    await user.click(await screen.findByRole('button', { name: 'Publier une nouvelle version' }))

    await user.type(screen.getByLabelText('Titre'), 'Charte 2026')
    await user.type(screen.getByLabelText('Contenu'), 'Règles d’usage du véhicule…')
    await user.click(screen.getByRole('button', { name: 'Publier' }))

    await waitFor(() => expect(charteCreate).toHaveBeenCalled())
    const formData = charteCreate.mock.calls[0][0]
    expect(formData instanceof FormData).toBe(true)
    expect(formData.get('document')).toBeTruthy()
  })
})
