import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ADSDEEP54 — boîte de réception des commentaires : fil chronologique filtrable
   (par ad/post, masqués, non répondus), actions inline (chacune = une
   proposition EngineAction), badge « caché-vérifié » (uniquement si
   hidden_verified), compteur cockpit, garde de réponse privée (1×/7 j). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  proposeHide: vi.fn(),
  proposeReply: vi.fn(),
  proposeDelete: vi.fn(),
  proposePrivateReply: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    comments: {
      list: mocks.list,
      proposeHide: mocks.proposeHide,
      proposeReply: mocks.proposeReply,
      proposeDelete: mocks.proposeDelete,
      proposePrivateReply: mocks.proposePrivateReply,
    },
  },
}))

import CommentsInboxScreen from './CommentsInboxScreen'

const recent = new Date(Date.now() - 60 * 60 * 1000).toISOString() // il y a 1 h
const older = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()
const stale = new Date(Date.now() - 9 * 24 * 60 * 60 * 1000).toISOString() // > 7 j

const COMMENTS = [
  { id: 1, meta_id: 'c1', object_meta_id: 'post-A', source: 'post',
    message: 'Bravo pour la pose', from_name: 'Ali', created_time: recent,
    is_hidden: false, hidden_verified: false, answered: false,
    private_reply_sent_at: null },
  { id: 2, meta_id: 'c2', object_meta_id: 'post-A', source: 'post',
    message: 'ARNAQUE totale', from_name: 'Troll', created_time: older,
    is_hidden: true, hidden_verified: true, answered: false,
    private_reply_sent_at: null },
  { id: 3, meta_id: 'c3', object_meta_id: 'dark-1', source: 'ad',
    message: 'Prix ?', from_name: 'Sara', created_time: older,
    is_hidden: true, hidden_verified: false, answered: false,
    private_reply_sent_at: null, ad_meta_id: 'ad-9' },
  { id: 4, meta_id: 'c4', object_meta_id: 'dark-1', source: 'ad',
    message: 'Merci répondu', from_name: 'Karim', created_time: stale,
    is_hidden: false, hidden_verified: false, answered: true,
    private_reply_sent_at: null },
]

const renderScreen = () => render(
  <MemoryRouter><CommentsInboxScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: COMMENTS })
  mocks.proposeHide.mockResolvedValue({ data: { id: 99 } })
  mocks.proposeReply.mockResolvedValue({ data: { id: 99 } })
  mocks.proposeDelete.mockResolvedValue({ data: { id: 99 } })
  mocks.proposePrivateReply.mockResolvedValue({ data: { id: 99 } })
})

describe('CommentsInboxScreen (ADSDEEP54)', () => {
  it('affiche le fil + le compteur cockpit', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(screen.getAllByTestId('ae-comment-card')).toHaveLength(4)
    expect(screen.getByTestId('ae-count-total')).toHaveTextContent('4')
    // 1 non répondu visible (c1 ; c2/c3 masqués, c4 répondu).
    expect(screen.getByTestId('ae-count-unanswered')).toHaveTextContent('1')
    expect(screen.getByTestId('ae-count-hidden')).toHaveTextContent('2')
  })

  it('badge « caché-vérifié » UNIQUEMENT si hidden_verified', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    // c2 : masqué + vérifié → badge vert.
    expect(screen.getByTestId('ae-hidden-verified-2')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-hidden-unverified-2')).not.toBeInTheDocument()
    // c3 : masqué mais NON vérifié → badge « non vérifié », jamais le vert.
    expect(screen.getByTestId('ae-hidden-unverified-3')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-hidden-verified-3')).not.toBeInTheDocument()
  })

  it('filtre « masqués seulement »', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-filter-hidden'))
    expect(screen.getAllByTestId('ae-comment-card')).toHaveLength(2) // c2 + c3
  })

  it('filtre par objet (post vs dark post)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('ae-filter-object'), { target: { value: 'dark-1' } })
    expect(screen.getAllByTestId('ae-comment-card')).toHaveLength(2) // c3 + c4
  })

  it('l’action masquer PROPOSE (règle #3)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-comment-hide-1'))
    await waitFor(() => expect(mocks.proposeHide).toHaveBeenCalledWith(1, { hidden: true }))
    expect(await screen.findByTestId('ae-proposed-1')).toBeInTheDocument()
  })

  it('réponse privée désactivée hors fenêtre 7 jours', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    // c1 récent → réponse privée disponible.
    expect(screen.getByTestId('ae-comment-private-1')).not.toBeDisabled()
    // c4 daté de > 7 jours → réponse privée bloquée.
    expect(screen.getByTestId('ae-comment-private-4')).toBeDisabled()
  })

  it('propose une réponse publique', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-comment-reply-1'))
    fireEvent.change(screen.getByTestId('ae-comment-reply-input-1'), { target: { value: 'Merci !' } })
    fireEvent.click(screen.getByTestId('ae-comment-reply-send-1'))
    await waitFor(() => expect(mocks.proposeReply).toHaveBeenCalledWith(1, { message: 'Merci !' }))
  })

  // ── PUB41 — Fraîcheur + panne visibles (sondage doux + état-erreur) ─────
  describe('PUB41 — sondage doux + état-erreur', () => {
    it('panne réseau -> message d’erreur, PAS « aucun commentaire »', async () => {
      mocks.list.mockRejectedValue(new Error('network'))
      renderScreen()
      expect(await screen.findByTestId('ae-comments-load-error')).toBeInTheDocument()
      expect(screen.queryByTestId('ae-comments-empty')).toBeNull()
    })

    it('boîte réellement vide (succès) -> état-vide normal, pas d’erreur', async () => {
      mocks.list.mockResolvedValue({ data: [] })
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      expect(screen.getByTestId('ae-comments-empty')).toBeInTheDocument()
      expect(screen.queryByTestId('ae-comments-load-error')).toBeNull()
    })

    it('bouton « Actualiser » redéclenche un chargement immédiat', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByTestId('ae-comments-refresh'))
      await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
    })
  })

  // ── PUB44 — Lien croisé vers la fiche « histoire complète » ─────────────
  describe('PUB44 — lien croisé vers la fiche ad', () => {
    it('commentaire avec ad_meta_id résolu -> lien affiché', async () => {
      renderScreen()
      const link = await screen.findByTestId('ae-comment-ad-link-3')
      expect(link).toHaveAttribute('href', '/publicite/ad/ad-9')
    })

    it('commentaire sans ad_meta_id (ex. post organique) -> aucun lien', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.list).toHaveBeenCalled())
      expect(screen.queryByTestId('ae-comment-ad-link-1')).toBeNull()
    })
  })
})
