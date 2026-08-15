import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR115 — smoke de l'écran Check-ins sécurité + SCAR : il se monte, charge la
   liste des check-ins, et déclenche un check-out via l'action de ligne. */

const scarCreate = vi.fn(() => Promise.resolve({ data: { id: 99 } }))
const scarRepondre = vi.fn(() => Promise.resolve({ data: {} }))
const scarVerifier = vi.fn(() => Promise.resolve({ data: {} }))

vi.mock('../../api/qhseApi', () => {
  const checkout = vi.fn(() => Promise.resolve({ data: {} }))
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
        list: () => Promise.resolve({
          data: [
            {
              id: 501, fournisseur_nom: 'Solar Import SARL',
              description_defaut: 'Onduleurs livrés hors spec', statut: 'emise',
              statut_display: 'Émise', echeance_reponse: '2026-08-01',
            },
            {
              id: 502, fournisseur_nom: 'Metal Structures SA',
              description_defaut: 'Structures corrodées', statut: 'repondue',
              statut_display: 'Répondue', echeance_reponse: '2026-08-05',
            },
          ],
        }),
        create: (...a) => scarCreate(...a),
        repondre: (...a) => scarRepondre(...a),
        verifier: (...a) => scarVerifier(...a),
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

beforeEach(() => {
  qhseApi.checkinsSecurite.checkout.mockClear()
  scarCreate.mockClear()
  scarRepondre.mockClear()
  scarVerifier.mockClear()
})
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

describe('WIR201 — SCAR fournisseur (cycle émise → répondue → vérifiée/close)', () => {
  it('crée une nouvelle SCAR depuis le bouton dédié', async () => {
    const user = userEvent.setup()
    renderScreen()
    await user.click(screen.getByRole('tab', { name: 'SCAR fournisseur' }))
    await screen.findAllByText('Solar Import SARL')

    await user.click(screen.getByRole('button', { name: /Nouvelle SCAR/ }))
    await user.type(screen.getByLabelText('ID fournisseur'), '7')
    await user.type(screen.getByLabelText('ID NCR source'), '33')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(scarCreate).toHaveBeenCalledWith(
      expect.objectContaining({ fournisseur: 7, ncr_source: 33 }),
    ))
  })

  it('propose « Répondre » sur une SCAR émise et l’envoie au serveur', async () => {
    const user = userEvent.setup()
    renderScreen()
    await user.click(screen.getByRole('tab', { name: 'SCAR fournisseur' }))
    await screen.findAllByText('Solar Import SARL')

    const btns = await screen.findAllByRole('button', { name: 'Répondre' })
    await user.click(btns[0])
    await user.type(screen.getByLabelText('Cause racine (fournisseur)'), 'Erreur de calibrage usine')
    await user.click(screen.getByRole('button', { name: 'Enregistrer la réponse' }))

    await waitFor(() => expect(scarRepondre).toHaveBeenCalledWith(
      501, expect.objectContaining({ cause_racine_fournisseur: 'Erreur de calibrage usine' }),
    ))
  })

  it('propose « Vérifier » sur une SCAR répondue et l’envoie au serveur', async () => {
    const user = userEvent.setup()
    renderScreen()
    await user.click(screen.getByRole('tab', { name: 'SCAR fournisseur' }))
    await screen.findAllByText('Metal Structures SA')

    const btns = await screen.findAllByRole('button', { name: 'Vérifier' })
    await user.click(btns[0])
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Vérifier' }))

    await waitFor(() => expect(scarVerifier).toHaveBeenCalledWith(
      502, expect.objectContaining({ efficace: 'true' }),
    ))
  })
})
