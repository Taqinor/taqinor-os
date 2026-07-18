import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XFLT12 — création véhicule avec pré-remplissage par modèle de référence.
   Vérifie que choisir un modèle pré-remplit les champs vides (marque, énergie,
   puissance fiscale) SANS écraser une saisie déjà faite, et que la création
   envoie bien `modele_ref` au serveur. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const vehiculesCreate = vi.fn(() => Promise.resolve({ data: { id: 1 } }))
const vehiculesList = vi.fn(() => Promise.resolve({ data: [] }))
const enginsCreate = vi.fn(() => Promise.resolve({ data: { id: 1 } }))
const enginsList = vi.fn(() => Promise.resolve({ data: [] }))
const modelesList = vi.fn(() => Promise.resolve({
  data: [{ id: 9, marque: 'Renault', modele: 'Kangoo', energie: 'diesel', puissance_fiscale: 5, valeur_catalogue: 180000 }],
}))

vi.mock('../../api/flotteApi', () => ({
  default: {
    vehicules: { create: (...args) => vehiculesCreate(...args), list: (...args) => vehiculesList(...args) },
    engins: { create: (...args) => enginsCreate(...args), list: (...args) => enginsList(...args) },
    modelesVehicule: { list: (...args) => modelesList(...args) },
  },
}))

import VehiculesList from './VehiculesList'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('VehiculeCreateDialog (XFLT12)', () => {
  it('pré-remplit énergie/puissance fiscale depuis le modèle choisi et envoie modele_ref', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculesList />)

    await user.click(await screen.findByRole('button', { name: 'Nouveau véhicule' }))
    await user.type(screen.getByLabelText('Immatriculation'), '12345-A-6')
    await user.selectOptions(screen.getByLabelText('Modèle de référence (catalogue)'), '9')

    expect(screen.getByLabelText('Marque')).toHaveValue('Renault')
    expect(screen.getByLabelText('Puissance fiscale (CV)')).toHaveValue(5)

    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(vehiculesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ immatriculation: '12345-A-6', modele_ref: 9 }),
    ))
  })

  it('n’écrase pas une marque déjà saisie à la sélection du modèle', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculesList />)

    await user.click(await screen.findByRole('button', { name: 'Nouveau véhicule' }))
    await user.type(screen.getByLabelText('Marque'), 'Dacia')
    await user.selectOptions(screen.getByLabelText('Modèle de référence (catalogue)'), '9')

    expect(screen.getByLabelText('Marque')).toHaveValue('Dacia')
  })
})

describe('EnginCreateDialog (WIR40)', () => {
  it('bascule sur « Engins » et crée un engin via le CRUD `engins/`', async () => {
    const user = userEvent.setup()
    withProviders(<VehiculesList />)

    await user.click(screen.getByRole('radio', { name: 'Engins' }))
    await user.click(await screen.findByRole('button', { name: 'Nouvel engin' }))

    await user.type(screen.getByLabelText('Désignation'), 'Nacelle Genie Z-45')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(enginsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Nacelle Genie Z-45', type_engin: 'nacelle' }),
    ))
  })
})
