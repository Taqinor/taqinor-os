import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../auth/store/authSlice'

/* AUDV11 — le cycle d'approbation de clôture NCR (ARC10 : démarrer / approuver
   / rejeter / escalader) et la création de SCAR depuis une NCR
   (`creer_scar_depuis_ncr`) étaient testés côté service
   (test_arc10_workflow_cloture_ncr.py, test_xqhs6_scar.py) sans AUCUN bouton
   d'écran — seule la clôture DIRECTE était atteignable, et le dialog SCAR
   passait par le CRUD générique au lieu du pont+validation serveur. Réseau
   mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

const NCR_ROW = {
  id: 7, reference: 'NCR-0007', titre: 'Casse verre', statut: 'ouverte',
  gravite: 'majeure', chantier_id: 42, date_detection: '2026-07-01',
  date_creation: '2026-07-01', disposition: null, fournisseur: 3,
}

const {
  empty, demarrerCloture, approuverCloture, rejeterCloture, escaladerCloture,
  creerScar,
} = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  demarrerCloture: vi.fn(() => Promise.resolve({
    data: { instance_id: 1, statut: 'en_cours', etape_courante: 1 },
  })),
  approuverCloture: vi.fn(() => Promise.resolve({
    data: { instance_id: 1, statut: 'en_cours', etape_courante: 2, ncr: NCR_ROW },
  })),
  rejeterCloture: vi.fn(() => Promise.resolve({
    data: { instance_id: 1, statut: 'termine', ncr: NCR_ROW },
  })),
  escaladerCloture: vi.fn(() => Promise.resolve({
    data: { step_id: 10, statut: 'escalade', ordre: 1 },
  })),
  creerScar: vi.fn(() => Promise.resolve({ data: { id: 55 } })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    nonConformites: {
      list: () => Promise.resolve({ data: [NCR_ROW] }),
      historique: empty,
      demarrerCloture: (...a) => demarrerCloture(...a),
      approuverCloture: (...a) => approuverCloture(...a),
      rejeterCloture: (...a) => rejeterCloture(...a),
      escaladerCloture: (...a) => escaladerCloture(...a),
      creerScar: (...a) => creerScar(...a),
    },
    capa: { list: empty, enRetard: empty },
    derogations: { list: empty, relancerDerogations: vi.fn(empty) },
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import NonConformites from './NonConformites'

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Responsable',
        permissions: [], isAuthenticated: true, loading: false,
      },
    },
  })
}

function withProviders(ui) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

async function ouvrirDetail() {
  withProviders(<NonConformites />)
  const matches = await screen.findAllByText('Casse verre')
  fireEvent.click(matches[0])
}

describe('NcrDetail — cycle d’approbation de clôture ARC10 (AUDV11)', () => {
  it('démarre le cycle de clôture', async () => {
    const user = userEvent.setup()
    await ouvrirDetail()
    await user.click(await screen.findByRole('button', { name: /Démarrer clôture/ }))
    await waitFor(() => expect(demarrerCloture).toHaveBeenCalledWith(7))
  })

  it('approuve l’étape courante', async () => {
    const user = userEvent.setup()
    await ouvrirDetail()
    await user.click(await screen.findByRole('button', { name: /Approuver l.étape/ }))
    await waitFor(() => expect(approuverCloture).toHaveBeenCalledWith(7))
  })

  it('rejette l’étape courante', async () => {
    const user = userEvent.setup()
    await ouvrirDetail()
    await user.click(await screen.findByRole('button', { name: /Rejeter l.étape/ }))
    await waitFor(() => expect(rejeterCloture).toHaveBeenCalledWith(7))
  })

  it('escalade l’étape en attente', async () => {
    const user = userEvent.setup()
    await ouvrirDetail()
    await user.click(await screen.findByRole('button', { name: /Escalader/ }))
    await waitFor(() => expect(escaladerCloture).toHaveBeenCalledWith(7))
  })
})

describe('NcrDetail — SCAR depuis une NCR route par le pont serveur (AUDV11)', () => {
  it('crée la SCAR via creer-scar (jamais le CRUD générique)', async () => {
    const user = userEvent.setup()
    await ouvrirDetail()
    await user.click(await screen.findByRole('button', { name: /Demander une action au fournisseur/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(
      within(dialog).getByPlaceholderText('Décrire le défaut constaté'),
      'Onduleur défectueux',
    )
    await user.click(within(dialog).getByRole('button', { name: 'Envoyer la demande' }))

    await waitFor(() => expect(creerScar).toHaveBeenCalledWith(7, expect.objectContaining({
      description_defaut: 'Onduleur défectueux',
    })))
  })
})
