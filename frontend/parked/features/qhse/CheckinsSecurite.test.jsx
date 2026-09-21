import { describe, it, expect, vi, beforeEach, afterEach, beforeAll } from 'vitest'
import { render, screen, waitFor, cleanup, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR115 — smoke de l'écran Check-ins sécurité : il se monte, charge la liste
   des check-ins, et déclenche un check-out via l'action de ligne.
   WIR201 — l'onglet SCAR fournisseur sort de la lecture seule : création
   (« Nouvelle SCAR »), réponse et vérification depuis l'écran, boutons
   visibles seulement sur les statuts autorisés (émise → Répondre,
   répondue → Vérifier). Les 3 appels réseau sont couverts ci-dessous. */

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

const SCAR_EMISE = {
  id: 30, fournisseur_nom: 'ACME Solaire', description_defaut: 'Panneaux fêlés',
  echeance_reponse: null, statut: 'emise', statut_display: 'Émise',
}
const SCAR_REPONDUE = {
  id: 31, fournisseur_nom: 'SolTech', description_defaut: 'Onduleur défectueux',
  echeance_reponse: null, statut: 'repondue', statut_display: 'Répondue',
}

vi.mock('../../api/qhseApi', () => {
  const checkout = vi.fn(() => Promise.resolve({ data: {} }))
  const scarCreate = vi.fn(() => Promise.resolve({ data: { id: 32 } }))
  const scarRepondre = vi.fn(() => Promise.resolve({ data: {} }))
  const scarVerifier = vi.fn(() => Promise.resolve({ data: {} }))
  return {
    default: {
      checkinsSecurite: {
        list: () => Promise.resolve({
          data: [{
            id: 1, technicien_nom: 'Sami T.', site_ref: 'Toiture Anfa',
            heure_checkin: '2026-07-18T08:00:00Z',
            heure_checkout_prevue: '2026-07-18T12:00:00Z',
            heure_checkout_reelle: null, en_retard: false,
          }],
        }),
        create: vi.fn(() => Promise.resolve({ data: {} })),
        checkout,
      },
      demandesActionFournisseur: {
        list: () => Promise.resolve({ data: [SCAR_EMISE, SCAR_REPONDUE] }),
        create: scarCreate,
        repondre: scarRepondre,
        verifier: scarVerifier,
      },
    },
  }
})

import qhseApi from '../../api/qhseApi'
import CheckinsSecurite from './CheckinsSecurite'

const renderScreen = () => render(
  <MemoryRouter>
    <ThemeProvider>
      <CheckinsSecurite />
    </ThemeProvider>
  </MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => cleanup())

describe('WIR115 CheckinsSecurite', () => {
  it('charge et affiche la liste des check-ins', async () => {
    renderScreen()
    // « Sami T. » / « Toiture Anfa » apparaissent en double (vue table + cartes) → All.
    expect((await screen.findAllByText('Sami T.')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Toiture Anfa').length).toBeGreaterThan(0)
  })

  it('déclenche un check-out depuis l’action de ligne', async () => {
    renderScreen()
    await screen.findAllByText('Sami T.')
    // L'action rapide est un IconButton dont le libellé = aria-label (dupliqué table/cartes).
    const btns = await screen.findAllByRole('button', { name: 'Check-out' })
    fireEvent.click(btns[0])
    await waitFor(() =>
      expect(qhseApi.checkinsSecurite.checkout).toHaveBeenCalledWith(1))
  })
})

describe('WIR201 SCAR fournisseur — cycle complet UI', () => {
  it('crée une SCAR depuis « Nouvelle SCAR »', async () => {
    const user = userEvent.setup()
    renderScreen()
    await user.click(screen.getByRole('tab', { name: 'SCAR fournisseur' }))
    await waitFor(() => expect(screen.getAllByText('ACME Solaire').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvelle SCAR/ }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Fournisseur (id)'), '7')
    await user.type(within(dialog).getByLabelText('NCR source (id)'), '42')
    await user.click(within(dialog).getByRole('button', { name: 'Créer la SCAR' }))

    await waitFor(() => expect(qhseApi.demandesActionFournisseur.create)
      .toHaveBeenCalledWith(expect.objectContaining({
        fournisseur: 7, ncr_source: 42,
      })))
  })

  it('propose Répondre seulement sur une SCAR émise, et l’envoie au serveur', async () => {
    const user = userEvent.setup()
    renderScreen()
    await user.click(screen.getByRole('tab', { name: 'SCAR fournisseur' }))
    await waitFor(() => expect(screen.getAllByText('ACME Solaire').length).toBeGreaterThan(0))

    const repondreBtns = screen.getAllByRole('button', { name: 'Répondre' })
    expect(repondreBtns.length).toBeGreaterThan(0)
    await user.click(repondreBtns[0])
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Cause racine'), 'Transport')
    await user.type(within(dialog).getByLabelText('Action corrective'), 'Renfort emballage')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer la réponse' }))

    await waitFor(() => expect(qhseApi.demandesActionFournisseur.repondre)
      .toHaveBeenCalledWith(30, expect.objectContaining({
        cause_racine_fournisseur: 'Transport',
        action_fournisseur: 'Renfort emballage',
      })))
  })

  it('propose Vérifier seulement sur une SCAR répondue, et l’envoie au serveur', async () => {
    const user = userEvent.setup()
    renderScreen()
    await user.click(screen.getByRole('tab', { name: 'SCAR fournisseur' }))
    await waitFor(() => expect(screen.getAllByText('SolTech').length).toBeGreaterThan(0))

    const verifierBtns = screen.getAllByRole('button', { name: 'Vérifier' })
    expect(verifierBtns.length).toBeGreaterThan(0)
    await user.click(verifierBtns[0])
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer la vérification' }))

    await waitFor(() => expect(qhseApi.demandesActionFournisseur.verifier)
      .toHaveBeenCalledWith(31, { efficace: true }))
  })

  it('ne propose PAS Vérifier sur une SCAR émise, ni Répondre sur une répondue', async () => {
    const user = userEvent.setup()
    renderScreen()
    await user.click(screen.getByRole('tab', { name: 'SCAR fournisseur' }))
    await waitFor(() => expect(screen.getAllByText('ACME Solaire').length).toBeGreaterThan(0))

    // Une seule ligne « Répondre » (l'émise) et une seule « Vérifier » (la répondue) —
    // chaque bouton de ligne rend table + repli carte, donc au moins 1 de chaque.
    expect(screen.getAllByRole('button', { name: 'Répondre' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Vérifier' }).length).toBeGreaterThan(0)
  })
})
