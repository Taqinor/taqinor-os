import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* ADSDEEP14 — Panneau « Créatif » du détail d'ad : vidéo jouable (URL fraîche
   mockée), texte complet, permalien IG, toggle preview, copier le texte. */

const mocks = vi.hoisted(() => ({ resolve: vi.fn(), preview: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: {
    media: { resolve: mocks.resolve },
    previews: { get: mocks.preview },
  },
}))

import AdCreativePanel from './AdCreativePanel'

const CREATIVE = {
  creative_meta_id: 'cr1',
  title: 'Devis gratuit',
  body: 'Passez au solaire et économisez',
  description: 'Installation clé en main',
  cta_type: 'MESSAGE_PAGE',
  video_id: 'v99',
  instagram_permalink_url: 'https://instagram.com/p/x',
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.resolve.mockResolvedValue({ data: { url: 'https://cdn.fb/v99.mp4', cached: false } })
  mocks.preview.mockResolvedValue({ data: { body: '<iframe src="prev"></iframe>' } })
})

describe('AdCreativePanel (ADSDEEP14)', () => {
  it('rend le texte complet du créatif', () => {
    render(<AdCreativePanel adMetaId="ad1" creative={CREATIVE} />)
    expect(screen.getByTestId('ae-creative-title')).toHaveTextContent('Devis gratuit')
    expect(screen.getByTestId('ae-creative-body')).toHaveTextContent('Passez au solaire')
    expect(screen.getByTestId('ae-creative-description')).toHaveTextContent('clé en main')
    expect(screen.getByTestId('ae-creative-cta')).toHaveTextContent('MESSAGE_PAGE')
  })

  it('résout et rend une vidéo <video> jouable depuis l\'URL fraîche', async () => {
    render(<AdCreativePanel adMetaId="ad1" creative={CREATIVE} />)
    await waitFor(() => expect(mocks.resolve).toHaveBeenCalledWith('v99', 'video'))
    const video = await screen.findByTestId('ae-creative-video-el')
    expect(video.tagName).toBe('VIDEO')
    expect(video).toHaveAttribute('src', 'https://cdn.fb/v99.mp4')
  })

  it('expose le permalien Instagram', () => {
    render(<AdCreativePanel adMetaId="ad1" creative={CREATIVE} />)
    expect(screen.getByTestId('ae-creative-ig-link'))
      .toHaveAttribute('href', 'https://instagram.com/p/x')
  })

  it('affiche l\'aperçu iframe au toggle', async () => {
    render(<AdCreativePanel adMetaId="ad1" creative={CREATIVE} />)
    fireEvent.click(screen.getByTestId('ae-creative-preview-toggle'))
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledWith('ad1', 'MOBILE_FEED_STANDARD'))
    expect(await screen.findByTestId('ae-creative-preview')).toBeInTheDocument()
  })

  it('copie le texte au clic', () => {
    const writeText = vi.fn()
    Object.assign(navigator, { clipboard: { writeText } })
    render(<AdCreativePanel adMetaId="ad1" creative={CREATIVE} />)
    fireEvent.click(screen.getByTestId('ae-creative-copy'))
    expect(writeText).toHaveBeenCalled()
    expect(screen.getByTestId('ae-creative-copy')).toHaveTextContent('Copié')
  })
})
