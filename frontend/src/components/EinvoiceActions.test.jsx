import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../api/einvoiceApi', () => ({
  default: {
    generer: vi.fn(),
    telecharger: vi.fn(() => Promise.resolve({ data: new Blob(['<xml/>']) })),
  },
}))
vi.mock('../utils/downloadBlob', () => ({ downloadBlob: vi.fn() }))

import einvoiceApi from '../api/einvoiceApi'
import { downloadBlob } from '../utils/downloadBlob'
import EinvoiceActions from './EinvoiceActions'

describe('EinvoiceActions (WIR106)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('génère une e-facture dry-run et propose le téléchargement du XML', async () => {
    einvoiceApi.generer.mockResolvedValueOnce({ status: 201, data: { id: 12, version: 1 } })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    await waitFor(() => expect(einvoiceApi.generer).toHaveBeenCalledWith(5, 'dry_run'))
    const dl = await screen.findByRole('button', { name: /Télécharger XML/ })
    fireEvent.click(dl)
    await waitFor(() => expect(einvoiceApi.telecharger).toHaveBeenCalledWith(12))
    await waitFor(() => expect(downloadBlob).toHaveBeenCalled())
  })

  it('affiche « désactivée » quand le serveur renvoie 204 (EINVOICE_ENABLED off)', async () => {
    einvoiceApi.generer.mockResolvedValueOnce({ status: 204, data: null })
    render(<EinvoiceActions factureId={5} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer e-facture/ }))
    expect(await screen.findByText(/E-facturation désactivée/)).toBeInTheDocument()
  })
})
