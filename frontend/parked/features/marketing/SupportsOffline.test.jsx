import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  qr: vi.fn(),
  downloadBlob: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    downloadBlob: mocks.downloadBlob,
    supportsOffline: { list: mocks.list, create: mocks.create, qr: mocks.qr },
  },
}))

import SupportsOffline from './SupportsOffline'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    data: [{ id: 1, nom: 'Flyer SIAM 2026', url_cible: 'https://taqinor.ma/contact?utm_source=offline', nb_scans: 12 }],
  })
})

describe('SupportsOffline', () => {
  it('affiche les supports avec leur compteur de scans', async () => {
    render(<SupportsOffline />)
    expect(await screen.findByText('Flyer SIAM 2026')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
  })

  it('créer un support envoie nom + url_cible', async () => {
    mocks.create.mockResolvedValue({ data: {} })
    render(<SupportsOffline />)
    await screen.findByText('Flyer SIAM 2026')
    fireEvent.change(screen.getByTestId('support-nom'), { target: { value: 'Bâche stand' } })
    fireEvent.change(screen.getByTestId('support-url'), { target: { value: 'https://taqinor.ma' } })
    fireEvent.click(screen.getByTestId('support-creer'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      { nom: 'Bâche stand', url_cible: 'https://taqinor.ma' }))
  })

  it('« Télécharger le QR » télécharge un SVG scannable', async () => {
    const blob = new Blob(['<svg></svg>'], { type: 'image/svg+xml' })
    mocks.qr.mockResolvedValue({ data: blob })
    render(<SupportsOffline />)
    await screen.findByText('Flyer SIAM 2026')
    fireEvent.click(screen.getByTestId('support-qr'))
    await waitFor(() => expect(mocks.qr).toHaveBeenCalledWith(1))
    expect(mocks.downloadBlob).toHaveBeenCalledWith(blob, 'qr-Flyer SIAM 2026.svg')
  })
})
