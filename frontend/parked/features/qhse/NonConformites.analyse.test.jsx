import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../auth/store/authSlice'

/* FE-XQHS5-13 (part XQHS7) — `AnalyseNcr` (5-Pourquoi / 8D) avait son modèle,
   son service et son action `analyse/`, mais aucun appelant : l'écran NCR
   n'offrait aucune surface d'analyse de cause. On vérifie le cycle lecture →
   saisie → enregistrement. Réseau mocké. */

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
  date_creation: '2026-07-01', disposition: null,
}

const { empty, analyse, depuisTicketSav } = vi.hoisted(() => ({
  empty: () => Promise.resolve({ data: [] }),
  depuisTicketSav: vi.fn(() => Promise.resolve({
    data: { id: 9, reference: 'NCR-0009' },
  })),
  analyse: vi.fn(() => Promise.resolve({
    data: {
      cinq_pourquoi: [{ pourquoi: 'Pourquoi la casse ?', reponse: 'Manutention' }],
      huit_d: { D4: { texte: 'Cause racine identifiée' } },
    },
  })),
}))

vi.mock('../../api/qhseApi', () => ({
  default: {
    nonConformites: {
      list: () => Promise.resolve({ data: [NCR_ROW] }),
      historique: empty,
      analyse: (...a) => analyse(...a),
      depuisTicketSav: (...a) => depuisTicketSav(...a),
    },
    capa: { list: empty, enRetard: empty },
    derogations: { list: empty },
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

async function ouvrirAnalyse(user) {
  withProviders(<NonConformites />)
  const matches = await screen.findAllByText('Casse verre')
  fireEvent.click(matches[0])
  await user.click(
    await screen.findByRole('tab', { name: 'Analyse 5-Pourquoi / 8D' }))
}

describe('NcrDetail — analyse 5-Pourquoi / 8D (FE-XQHS7)', () => {
  it('lit l’analyse existante et pré-remplit les champs', async () => {
    const user = userEvent.setup()
    await ouvrirAnalyse(user)

    expect(await screen.findByLabelText('Pourquoi 1')).toHaveValue('Pourquoi la casse ?')
    expect(screen.getByLabelText('Réponse 1')).toHaveValue('Manutention')
    expect(screen.getByLabelText('D4 — Cause racine')).toHaveValue('Cause racine identifiée')
    // Une lecture ne pousse aucune donnée (POST sans corps).
    expect(analyse).toHaveBeenCalledWith(7)
  })

  it('n’envoie que les « pourquoi » renseignés (borne serveur à 5)', async () => {
    const user = userEvent.setup()
    await ouvrirAnalyse(user)
    await screen.findByLabelText('Pourquoi 2')

    await user.type(screen.getByLabelText('Pourquoi 2'), 'Pourquoi la manutention ?')
    await user.click(screen.getByRole('button', { name: /Enregistrer l’analyse/ }))

    await waitFor(() => expect(analyse).toHaveBeenCalledWith(7, expect.objectContaining({
      cinq_pourquoi: [
        { pourquoi: 'Pourquoi la casse ?', reponse: 'Manutention' },
        { pourquoi: 'Pourquoi la manutention ?', reponse: '' },
      ],
    })))
  })
})

/* FE-XQHS23 — le pont ticket SAV → NCR (`depuis-ticket-sav/`, idempotent)
   était le seul des deux ponts sans aucun appelant côté écran. */
describe('NcrRegister — NCR depuis un ticket SAV (FE-XQHS23)', () => {
  it('crée la NCR à partir de l’identifiant du ticket', async () => {
    const user = userEvent.setup()
    withProviders(<NonConformites />)

    await user.click(await screen.findByRole('button', { name: /Depuis un ticket SAV/ }))
    await user.type(await screen.findByLabelText('Ticket SAV (id)'), '31')
    await user.click(screen.getByRole('button', { name: 'Créer la NCR' }))

    await waitFor(() => expect(depuisTicketSav).toHaveBeenCalledWith(
      { ticket: 31, gravite: 'mineure' },
    ))
  })
})
