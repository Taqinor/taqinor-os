import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTCON23 — assistant guidé « Créer un chantier BTP » : 4 étapes enchaînées
   sur des endpoints déjà construits, brouillon local repris après abandon. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const api = vi.hoisted(() => ({
  lotsCreate: vi.fn(),
  definirChecklist: vi.fn(() => Promise.resolve({ data: {} })),
  ppspsCreate: vi.fn(() => Promise.resolve({ data: { id: 77 } })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    lots: {
      create: (...a) => api.lotsCreate(...a),
      definirChecklist: (...a) => api.definirChecklist(...a),
    },
    ppsps: { create: (...a) => api.ppspsCreate(...a) },
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
    getSousTraitants: () => Promise.resolve({
      data: { results: [{ id: 9, nom: 'ELEC SARL' }] },
    }),
  },
}))

import NouveauChantierBtpWizard from './NouveauChantierBtpWizard'
import {
  BROUILLON_CLE, chargerBrouillon, effacerBrouillon,
} from './nouveauChantierBtp.utils'

let compteurLot = 0

beforeEach(() => {
  vi.clearAllMocks()
  compteurLot = 0
  api.lotsCreate.mockImplementation(() => {
    compteurLot += 1
    return Promise.resolve({ data: { id: 100 + compteurLot } })
  })
  window.localStorage.clear()
})

function afficher() {
  return render(
    <MemoryRouter>
      <ThemeProvider><NouveauChantierBtpWizard /></ThemeProvider>
    </MemoryRouter>,
  )
}

async function etape1(user) {
  const select = await screen.findByLabelText('Chantier cible')
  await user.selectOptions(
    select, within(select).getByRole('option', { name: /Villa Zenith/ }))
  await user.click(screen.getByRole('button', { name: 'Suivant' }))
}

describe('NouveauChantierBtpWizard (NTCON23)', () => {
  it('bloque l’étape 1 tant qu’aucun chantier n’est choisi', async () => {
    afficher()
    await screen.findByLabelText('Chantier cible')
    expect(screen.getByRole('button', { name: 'Suivant' }).disabled).toBe(true)
  })

  it('propose les lots types puis les rend éditables', async () => {
    const user = userEvent.setup()
    afficher()
    await etape1(user)

    await user.click(
      screen.getByRole('button', { name: 'Proposer les lots types' }))
    const premier = await screen.findByLabelText('Nom du lot 1')
    expect(premier.value).toBe('Gros-œuvre')

    await user.clear(premier)
    await user.type(premier, 'Terrassement')
    expect(screen.getByLabelText('Nom du lot 1').value).toBe('Terrassement')
  })

  it('enregistre un brouillon repris au rechargement', async () => {
    const user = userEvent.setup()
    const vue = afficher()
    await etape1(user)
    await user.click(
      screen.getByRole('button', { name: 'Proposer les lots types' }))

    await waitFor(() => {
      expect(window.localStorage.getItem(BROUILLON_CLE)).toBeTruthy()
    })
    const brouillon = chargerBrouillon()
    expect(brouillon.chantier).toBe('5')
    expect(brouillon.lots.length).toBe(5)

    vue.unmount()
    afficher()
    // Le chantier du brouillon est déjà sélectionné à la reprise (les options
    // du sélecteur arrivent de façon asynchrone).
    const select = await screen.findByLabelText('Chantier cible')
    await waitFor(() => expect(select.value).toBe('5'))
  })

  it('crée les lots, la checklist et le PPSPS en une session', async () => {
    const user = userEvent.setup()
    afficher()
    await etape1(user)

    // Étape 2 — un seul lot, saisi à la main.
    await user.click(screen.getByRole('button', { name: 'Ajouter un lot' }))
    await user.type(screen.getByLabelText('Nom du lot 1'), 'Gros-œuvre')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))

    // Étape 3 — sous-traité.
    await user.click(
      screen.getByLabelText('Lot Gros-œuvre exécuté en interne'))
    const selectSt = await screen.findByLabelText(
      'Sous-traitant du lot Gros-œuvre')
    await user.selectOptions(
      selectSt, within(selectSt).getByRole('option', { name: 'ELEC SARL' }))
    await user.click(screen.getByRole('button', { name: 'Suivant' }))

    // Étape 4 — PPSPS optionnel renseigné.
    await user.type(screen.getByLabelText('Titre du PPSPS'), 'PPSPS Villa')
    await user.click(
      screen.getByRole('button', { name: 'Créer le chantier BTP' }))

    await waitFor(() => expect(api.lotsCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        chantier: '5', nom: 'Gros-œuvre', interne: false, sous_traitant: 9,
      })))
    await waitFor(() => expect(api.definirChecklist).toHaveBeenCalledWith(101, []))
    await waitFor(() => expect(api.ppspsCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        chantier: '5', titre: 'PPSPS Villa', lots_couverts: [101],
      })))
    expect(await screen.findByTestId('btp-wizard-resultat')).toBeTruthy()
    // Le brouillon est purgé une fois le chantier initialisé.
    expect(window.localStorage.getItem(BROUILLON_CLE)).toBeNull()
  })

  it('n’appelle pas le PPSPS quand l’étape est laissée vide', async () => {
    const user = userEvent.setup()
    afficher()
    await etape1(user)
    await user.click(screen.getByRole('button', { name: 'Ajouter un lot' }))
    await user.type(screen.getByLabelText('Nom du lot 1'), 'Finitions')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(
      screen.getByRole('button', { name: 'Créer le chantier BTP' }))

    await waitFor(() => expect(api.lotsCreate).toHaveBeenCalled())
    expect(api.ppspsCreate).not.toHaveBeenCalled()
  })
})

describe('brouillon local (NTCON23)', () => {
  it('reste fonctionnel si localStorage est indisponible', () => {
    const original = window.localStorage.getItem
    window.localStorage.getItem = () => { throw new Error('bloqué') }
    expect(chargerBrouillon().lots).toEqual([])
    window.localStorage.getItem = original
    expect(effacerBrouillon()).toBe(true)
  })
})
