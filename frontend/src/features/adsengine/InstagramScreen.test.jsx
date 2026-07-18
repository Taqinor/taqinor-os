import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ADSDEEP56 — écran Instagram : grille de médias + métriques, composeur de
   publication (programmable, légende LECTURE SEULE avertie), quota 50/24 h,
   gestion des commentaires IG (masquer/répondre/supprimer + couper les
   commentaires). Chaque écriture PROPOSE une EngineAction (règle #3). */

const mocks = vi.hoisted(() => ({
  media: vi.fn(),
  comments: vi.fn(),
  quota: vi.fn(),
  proposePublish: vi.fn(),
  proposeHideComment: vi.fn(),
  proposeReplyComment: vi.fn(),
  proposeDeleteComment: vi.fn(),
  proposeToggleComments: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    instagram: {
      media: mocks.media,
      comments: mocks.comments,
      quota: mocks.quota,
      proposePublish: mocks.proposePublish,
      proposeHideComment: mocks.proposeHideComment,
      proposeReplyComment: mocks.proposeReplyComment,
      proposeDeleteComment: mocks.proposeDeleteComment,
      proposeToggleComments: mocks.proposeToggleComments,
    },
  },
}))

import InstagramScreen from './InstagramScreen'

const MEDIA = [
  { id: 1, meta_id: 'm-1', caption: 'Belle installation', media_type: 'IMAGE',
    media_url: 'https://ig/m1.jpg', like_count: 12, comments_count: 2,
    view_count: 0, comment_enabled: true },
  { id: 2, meta_id: 'm-2', caption: 'Notre Reel', media_type: 'REELS',
    media_url: '', like_count: 40, comments_count: 5, view_count: 900,
    comment_enabled: false },
]
const COMMENTS = [
  { id: 10, meta_id: 'igc-10', media_meta_id: 'm-1', message: 'Prix ?',
    from_username: 'sara', hidden: false },
  { id: 11, meta_id: 'igc-11', media_meta_id: 'm-1', message: 'spam',
    from_username: 'troll', hidden: true },
]
const QUOTA = { used: 4, total: 50, remaining: 46 }

const renderScreen = () => render(
  <MemoryRouter><InstagramScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.media.mockResolvedValue({ data: MEDIA })
  mocks.comments.mockResolvedValue({ data: COMMENTS })
  mocks.quota.mockResolvedValue({ data: QUOTA })
  mocks.proposePublish.mockResolvedValue({ data: { id: 1 } })
  mocks.proposeHideComment.mockResolvedValue({ data: { id: 1 } })
  mocks.proposeReplyComment.mockResolvedValue({ data: { id: 1 } })
  mocks.proposeDeleteComment.mockResolvedValue({ data: { id: 1 } })
  mocks.proposeToggleComments.mockResolvedValue({ data: { id: 1 } })
})

describe('InstagramScreen (ADSDEEP56)', () => {
  it('affiche la grille de médias + le quota', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.media).toHaveBeenCalled())
    expect(screen.getAllByTestId('ae-ig-media-card')).toHaveLength(2)
    expect(screen.getByTestId('ae-ig-quota')).toHaveTextContent('4/50')
    // Légende marquée LECTURE SEULE.
    expect(screen.getByTestId('ae-ig-caption-readonly-1')).toBeInTheDocument()
  })

  it('le composeur avertit que la légende est immuable et PROPOSE la publication', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.media).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-ig-toggle-composer'))
    // Avertissement légende immuable.
    expect(screen.getByTestId('ae-ig-caption-warning')).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('ae-ig-url'), { target: { value: 'https://img/x.jpg' } })
    fireEvent.change(screen.getByTestId('ae-ig-caption'), { target: { value: 'Ma légende' } })
    fireEvent.click(screen.getByTestId('ae-ig-publish'))
    await waitFor(() => expect(mocks.proposePublish).toHaveBeenCalled())
    const payload = mocks.proposePublish.mock.calls[0][0]
    expect(payload.media_type).toBe('IMAGE')
    expect(payload.image_url).toBe('https://img/x.jpg')
    expect(payload.caption).toBe('Ma légende')
    expect(await screen.findByTestId('ae-ig-composer-msg')).toBeInTheDocument()
  })

  it('publie un Reel via video_url quand le type est REELS', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.media).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-ig-toggle-composer'))
    fireEvent.change(screen.getByTestId('ae-ig-type'), { target: { value: 'REELS' } })
    fireEvent.change(screen.getByTestId('ae-ig-url'), { target: { value: 'https://v/reel.mp4' } })
    fireEvent.click(screen.getByTestId('ae-ig-publish'))
    await waitFor(() => expect(mocks.proposePublish).toHaveBeenCalled())
    const payload = mocks.proposePublish.mock.calls[0][0]
    expect(payload.media_type).toBe('REELS')
    expect(payload.video_url).toBe('https://v/reel.mp4')
    expect(payload.image_url).toBe('')
  })

  it('les commentaires IG sont gérables (masquer PROPOSE)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.media).toHaveBeenCalled())
    expect(screen.getByTestId('ae-ig-comments-1')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('ae-ig-comment-hide-10'))
    await waitFor(() => expect(mocks.proposeHideComment).toHaveBeenCalledWith(10, { hidden: true }))
    expect(await screen.findByTestId('ae-ig-proposed-c-10')).toBeInTheDocument()
  })

  it('couper les commentaires d’un média PROPOSE', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.media).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-ig-toggle-comments-1'))
    await waitFor(() => expect(mocks.proposeToggleComments).toHaveBeenCalledWith('m-1', { enabled: false }))
  })
})
