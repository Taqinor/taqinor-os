import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* MSGACC1 — écran d'envoi des messages d'accueil (Paramètres). Prouve :
   - le payload exact envoyé (destinataire number, corps, visible_a_partir_de
     ISO combinée date+heure) ;
   - erreurs par champ (400 -> sous le champ concerné) ;
   - la liste des envois + suppression (refusée si déjà lu → bouton absent). */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn() },
}))
vi.mock('../../api/notificationsApi', () => ({
  default: {
    getMessagesAccueil: vi.fn(),
    createMessageAccueil: vi.fn(),
    deleteMessageAccueil: vi.fn(),
  },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({
    confirm: () => Promise.resolve(true),
    confirmDelete: () => Promise.resolve(true),
  }),
}))
// MicDicteeButton se rend `null` en jsdom (pas de Web Speech) — pas besoin de
// le mocker, mais on neutralise tout écran de rendu superflu au besoin.

import api from '../../api/axios'
import notificationsApi from '../../api/notificationsApi'
import MessagesAccueilPage from './MessagesAccueilPage'

const USERS = [
  { id: 1, username: 'reda', is_active: true },
  { id: 2, username: 'inactif', is_active: false },
]

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: USERS })
  notificationsApi.getMessagesAccueil.mockResolvedValue({ data: { results: [] } })
  notificationsApi.createMessageAccueil.mockResolvedValue({ data: { id: 99 } })
  notificationsApi.deleteMessageAccueil.mockResolvedValue({})
})

describe('MSGACC1 — MessagesAccueilPage', () => {
  it('ne propose que les utilisateurs ACTIFS dans le sélecteur destinataire', async () => {
    render(<MessagesAccueilPage />)
    await userEvent.click(screen.getByRole('combobox'))
    expect(await screen.findByRole('option', { name: 'reda' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'inactif' })).not.toBeInTheDocument()
  })

  it('envoie le payload exact (destinataire number, corps, date+heure ISO)', async () => {
    render(<MessagesAccueilPage />)

    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(await screen.findByRole('option', { name: 'reda' }))

    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-09-16' } })
    fireEvent.change(screen.getByLabelText('Heure'), { target: { value: '08:00' } })
    await userEvent.type(screen.getByLabelText('Message'), 'Bonjour l’équipe')

    await userEvent.click(screen.getByRole('button', { name: 'Envoyer le message' }))

    await waitFor(() => expect(notificationsApi.createMessageAccueil).toHaveBeenCalled())
    const payload = notificationsApi.createMessageAccueil.mock.calls[0][0]
    expect(payload.destinataire).toBe(1)
    expect(payload.corps).toBe('Bonjour l’équipe')
    expect(payload.visible_a_partir_de).toBe(
      new Date('2026-09-16T08:00:00').toISOString(),
    )
  })

  it('erreur 400 par champ — message EXACT sous le champ + bandeau qui nomme le champ', async () => {
    notificationsApi.createMessageAccueil.mockRejectedValueOnce({
      response: { status: 400, data: { corps: ['Le corps du message est requis.'] } },
    })
    render(<MessagesAccueilPage />)

    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(await screen.findByRole('option', { name: 'reda' }))
    // Le bouton d'envoi est désactivé sans corps ; on force la soumission via
    // le formulaire pour exercer le chemin d'erreur serveur.
    await userEvent.type(screen.getByLabelText('Message'), ' ')
    await userEvent.click(screen.getByRole('button', { name: 'Envoyer le message' }))

    // Sous le champ — id déterministe posé par FormField (`${id}-error`) ;
    // `toHaveTextContent` ignore le préfixe sr-only « Champ requis : ».
    await waitFor(() => expect(document.getElementById('msgacc-corps-error'))
      .toHaveTextContent('Le corps du message est requis.'))
    // Bandeau — nomme le champ EN FRANÇAIS, jamais la clé technique brute.
    expect(screen.getByText('Message : Le corps du message est requis.')).toBeInTheDocument()
  })

  it('liste les messages envoyés avec leur statut, supprime si non lu', async () => {
    notificationsApi.getMessagesAccueil.mockResolvedValue({
      data: {
        results: [
          { id: 5, destinataire_nom: 'reda', visible_a_partir_de: '2026-09-16T08:00:00Z', lu_le: null },
          { id: 6, destinataire_nom: 'sami', visible_a_partir_de: '2026-09-16T08:00:00Z', lu_le: '2026-09-16T09:00:00Z' },
        ],
      },
    })
    render(<MessagesAccueilPage />)

    const grid = await screen.findByRole('grid', { name: 'Messages d’accueil envoyés' })
    const rowReda = within(grid).getByText('reda').closest('tr')
    const rowSami = within(grid).getByText('sami').closest('tr')
    expect(within(rowReda).getByText('Non lu')).toBeInTheDocument()
    expect(within(rowSami).getByText(/Lu le/)).toBeInTheDocument()

    // Suppression proposée seulement pour le message NON lu.
    expect(within(rowReda).getByRole('button', { name: 'Supprimer' })).toBeInTheDocument()
    expect(within(rowSami).queryByRole('button', { name: 'Supprimer' })).not.toBeInTheDocument()

    await userEvent.click(within(rowReda).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(notificationsApi.deleteMessageAccueil).toHaveBeenCalledWith(5))
  })
})
