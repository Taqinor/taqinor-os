import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* MSGACC1 — modale d'accueil : affichée dès qu'un message est dû et non lu,
   « Compris » poste la lecture puis passe au suivant, et un échec réseau
   (fetch ou lecture) reste SILENCIEUX — jamais bloquer l'ouverture de l'ERP. */

const { messagesAccueilALire, marquerMessageAccueilLu, navigate } = vi.hoisted(() => ({
  messagesAccueilALire: vi.fn(),
  marquerMessageAccueilLu: vi.fn(() => Promise.resolve({ data: {} })),
  navigate: vi.fn(),
}))
vi.mock('../api/notificationsApi', () => ({
  default: { messagesAccueilALire, marquerMessageAccueilLu },
}))
// AMENDEMENT FONDATEUR — le composant est monté HORS de l'arbre du routeur
// (voir son commentaire) : les chemins internes naviguent via `router.
// navigate()`, jamais <Link> (pas de contexte React Router disponible ici).
vi.mock('../router', () => ({ default: { navigate } }))

import MessageAccueilModal from './MessageAccueilModal'

function renderWith(isAuthenticated) {
  const store = configureStore({ reducer: { auth: (s = { isAuthenticated }) => s } })
  return render(
    <Provider store={store}>
      <MessageAccueilModal />
    </Provider>,
  )
}

afterEach(() => cleanup())
beforeEach(() => vi.clearAllMocks())

describe('MSGACC1 — MessageAccueilModal', () => {
  it('rien tant que non authentifié — aucun fetch', () => {
    renderWith(false)
    expect(messagesAccueilALire).not.toHaveBeenCalled()
    expect(screen.queryByTestId('message-accueil')).not.toBeInTheDocument()
  })

  it('affiche le message dû, auteur et corps', async () => {
    messagesAccueilALire.mockResolvedValueOnce({
      data: {
        messages: [{
          id: 1, auteur_nom: 'Reda', visible_a_partir_de: '2026-09-16T07:00:00Z',
          corps: 'Bonjour !\n\nUn message.',
        }],
      },
    })
    renderWith(true)
    expect(await screen.findByTestId('message-accueil')).toBeInTheDocument()
    expect(screen.getByText(/Message d.accueil/i)).toBeInTheDocument()
    expect(screen.getByText(/Reda/)).toBeInTheDocument()
    expect(screen.getByText(/Un message\./)).toBeInTheDocument()
  })

  it('auteur absent → « Direction »', async () => {
    messagesAccueilALire.mockResolvedValueOnce({
      data: { messages: [{ id: 1, auteur_nom: null, visible_a_partir_de: null, corps: 'Bonjour' }] },
    })
    renderWith(true)
    expect(await screen.findByText(/Direction/)).toBeInTheDocument()
  })

  it('« Compris » poste la lecture et passe au message suivant', async () => {
    messagesAccueilALire.mockResolvedValueOnce({
      data: {
        messages: [
          { id: 1, auteur_nom: 'Reda', visible_a_partir_de: null, corps: 'Premier message' },
          { id: 2, auteur_nom: 'Reda', visible_a_partir_de: null, corps: 'Second message' },
        ],
      },
    })
    renderWith(true)
    expect(await screen.findByText('Premier message')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Compris' }))
    expect(marquerMessageAccueilLu).toHaveBeenCalledWith(1)
    expect(await screen.findByText('Second message')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Compris' }))
    expect(marquerMessageAccueilLu).toHaveBeenCalledWith(2)
    await waitFor(() => {
      expect(screen.queryByTestId('message-accueil')).not.toBeInTheDocument()
    })
  })

  it('aucun message dû — rien ne s’affiche', async () => {
    messagesAccueilALire.mockResolvedValueOnce({ data: { messages: [] } })
    renderWith(true)
    await waitFor(() => expect(messagesAccueilALire).toHaveBeenCalled())
    expect(screen.queryByTestId('message-accueil')).not.toBeInTheDocument()
  })

  it('échec réseau du fetch — silencieux, jamais de crash', async () => {
    messagesAccueilALire.mockRejectedValueOnce(new Error('réseau'))
    renderWith(true)
    await waitFor(() => expect(messagesAccueilALire).toHaveBeenCalled())
    expect(screen.queryByTestId('message-accueil')).not.toBeInTheDocument()
  })

  it('échec réseau de la lecture — la modale avance quand même (jamais bloquant)', async () => {
    marquerMessageAccueilLu.mockRejectedValueOnce(new Error('réseau'))
    messagesAccueilALire.mockResolvedValueOnce({
      data: { messages: [{ id: 1, auteur_nom: 'Reda', visible_a_partir_de: null, corps: 'Seul message' }] },
    })
    renderWith(true)
    expect(await screen.findByText('Seul message')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Compris' }))
    await waitFor(() => {
      expect(screen.queryByTestId('message-accueil')).not.toBeInTheDocument()
    })
  })

  it('un chemin interne (/ged) rend un lien cliquable qui ferme la modale puis navigue', async () => {
    messagesAccueilALire.mockResolvedValueOnce({
      data: {
        messages: [{
          id: 1, auteur_nom: 'Reda', visible_a_partir_de: null,
          corps: 'Ouvre-les ici : /ged',
        }],
      },
    })
    renderWith(true)
    const lien = await screen.findByRole('button', { name: '/ged' })
    expect(lien).toBeInTheDocument()

    await userEvent.click(lien)
    expect(navigate).toHaveBeenCalledWith('/ged')
    // Rien n'est marqué lu par un clic-lien (ce n'est pas « Compris ») —
    // seule la fermeture immédiate de la modale est garantie.
    expect(marquerMessageAccueilLu).not.toHaveBeenCalled()
    await waitFor(() => {
      expect(screen.queryByTestId('message-accueil')).not.toBeInTheDocument()
    })
  })

  it('un texte SANS chemin interne ne produit aucun bouton dans le corps', async () => {
    messagesAccueilALire.mockResolvedValueOnce({
      data: { messages: [{ id: 1, auteur_nom: 'Reda', visible_a_partir_de: null, corps: 'Bonjour, rien à cliquer ici.' }] },
    })
    renderWith(true)
    await screen.findByTestId('message-accueil')
    // Seul le bouton « Compris » doit exister — aucun lien-chemin inventé.
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })

  it('un seul fetch même si le composant se re-rend', async () => {
    messagesAccueilALire.mockResolvedValueOnce({ data: { messages: [] } })
    const { rerender } = renderWith(true)
    await waitFor(() => expect(messagesAccueilALire).toHaveBeenCalledTimes(1))
    const store = configureStore({ reducer: { auth: (s = { isAuthenticated: true }) => s } })
    rerender(
      <Provider store={store}>
        <MessageAccueilModal />
      </Provider>,
    )
    expect(messagesAccueilALire).toHaveBeenCalledTimes(1)
  })

  it('HOTFIX — un corps très long garde « Compris » atteignable (corps défilant, jamais hors écran)', async () => {
    messagesAccueilALire.mockResolvedValue({
      data: { messages: [{ id: 9, auteur_nom: null, visible_a_partir_de: '2026-09-15T06:00:00Z', corps: 'Ligne\n'.repeat(400) }] },
    })
    renderWith(true)
    await screen.findByTestId('message-accueil')
    // Le CORPS défile (et lui seul) : c'est ce qui garantit que le pied de
    // carte — donc « Compris » — reste visible quelle que soit la longueur.
    const corps = screen.getByTestId('message-accueil-corps')
    expect(corps.className).toContain('overflow-y-auto')
    // La carte est bornée en hauteur (85vh) : sans cette borne, le corps ne
    // défile jamais et pousse le pied hors écran (l'incident du 15/09).
    const carte = corps.parentElement
    expect(carte.className).toContain('max-h-[85vh]')
    expect(screen.getByRole('button', { name: 'Compris' })).toBeInTheDocument()
  })
})
