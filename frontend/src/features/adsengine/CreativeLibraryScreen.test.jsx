import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG27 — Bibliothèque créative : grille d'assets, flux policy-check humain
   règle par règle (pending → vérifié à l'écran), upload, variantes ENG18. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  policyCheck: vi.fn(),
  generateVariants: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    creatives: {
      list: mocks.list, upload: mocks.upload,
      policyCheck: mocks.policyCheck, generateVariants: mocks.generateVariants,
    },
  },
}))

import CreativeLibraryScreen from './CreativeLibraryScreen'

const renderScreen = () => render(
  <MemoryRouter><CreativeLibraryScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    { id: 1, designation: 'Reel toiture', type: 'reel', policy_stamp: { passed: false }, reponses_whatsapp: 3, cout_mad: 250 },
    { id: 2, designation: 'Statique prix', type: 'static', policy_stamp: { passed: true }, reponses_whatsapp: 8, cout_mad: 400 },
  ] })
  mocks.upload.mockResolvedValue({ data: {} })
  mocks.policyCheck.mockResolvedValue({ data: {} })
  mocks.generateVariants.mockResolvedValue({ data: {} })
})

describe('CreativeLibraryScreen (ENG27)', () => {
  it('affiche la grille avec statut de conformité et perf par asset', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(screen.getAllByTestId('ae-creative-card')).toHaveLength(2)
    expect(screen.getByTestId('ae-creative-status-1')).toHaveTextContent('À vérifier')
    expect(screen.getByTestId('ae-creative-status-2')).toHaveTextContent('Vérifié')
    expect(screen.getByText(/3 réponses WhatsApp/)).toBeInTheDocument()
  })

  it('ADSDEEP15 — rend un <video> pour un reel avec preview_url et un <img> pour un statique', async () => {
    mocks.list.mockResolvedValue({ data: [
      { id: 10, designation: 'Reel', asset_type: 'reel', is_video: true,
        preview_url: 'https://minio/signed/reel.mp4', policy_stamp: { passed: true } },
      { id: 11, designation: 'Statique', asset_type: 'static', is_video: false,
        preview_url: 'https://minio/signed/img.png', policy_stamp: { passed: true } },
    ] })
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    const video = await screen.findByTestId('ae-creative-video')
    expect(video.tagName).toBe('VIDEO')
    expect(video).toHaveAttribute('src', 'https://minio/signed/reel.mp4')
    expect(screen.getByTestId('ae-creative-img')).toHaveAttribute('src', 'https://minio/signed/img.png')
  })

  it('policy-check humain : l\'asset passe pending → vérifié une fois toutes les règles confirmées', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-creative-check-1'))
    const checklist = await screen.findByTestId('ae-creative-checklist-1')
    // Valider est désactivé tant que TOUTES les règles ne sont pas confirmées.
    const validate = screen.getByTestId('ae-creative-validate-1')
    expect(validate).toBeDisabled()
    // Confirme chaque règle (rule-by-rule).
    const boxes = checklist.querySelectorAll('input[type="checkbox"]')
    expect(boxes.length).toBeGreaterThanOrEqual(3)
    boxes.forEach(b => fireEvent.click(b))
    expect(validate).not.toBeDisabled()
    fireEvent.click(validate)
    await waitFor(() => expect(mocks.policyCheck).toHaveBeenCalledWith(1, expect.objectContaining({ passed: true })))
    // pending → vérifié à l'écran.
    await waitFor(() => expect(screen.getByTestId('ae-creative-status-1')).toHaveTextContent('Vérifié'))
  })

  it('upload : soumet un FormData avec le fichier choisi', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('ae-creative-upload-designation'),
      { target: { value: 'Nouveau reel' } })
    const file = new File(['x'], 'reel.mp4', { type: 'video/mp4' })
    fireEvent.change(screen.getByTestId('ae-creative-upload-file'),
      { target: { files: [file] } })
    fireEvent.click(screen.getByTestId('ae-creative-upload-submit'))
    await waitFor(() => expect(mocks.upload).toHaveBeenCalled())
    const fd = mocks.upload.mock.calls[0][0]
    expect(fd).toBeInstanceOf(FormData)
    expect(fd.get('designation')).toBe('Nouveau reel')
    expect(fd.get('file')).toBeTruthy()
  })

  it('déclenche des variantes (ENG18) sur un asset vérifié', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('ae-creative-variants-2'))
    await waitFor(() => expect(mocks.generateVariants).toHaveBeenCalledWith(2))
  })
})
