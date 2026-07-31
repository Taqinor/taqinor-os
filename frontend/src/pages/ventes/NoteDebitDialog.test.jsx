import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR103 — note de débit (ZFAC4) : le backend était complet et testé, l'écran
   Facturation n'avait AUCUNE UI. Ce test verrouille les trois appels qui
   rendent la fonctionnalité réellement utilisable : lister, créer, télécharger
   le PDF. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: {
    getNotesDebit: vi.fn(() => Promise.resolve({
      data: [{ id: 3, reference: 'ND-202607-0001', total_ttc: '1200.00' }],
    })),
    creerNoteDebit: vi.fn(() => Promise.resolve({
      data: { id: 4, reference: 'ND-202607-0002', total_ttc: '600.00' },
    })),
    telechargerNoteDebitPdf: vi.fn(() => Promise.resolve({ data: new Blob() })),
  },
}))
vi.mock('../../utils/pdfBlob', () => ({
  openPdfBlob: vi.fn(),
  openPdfInGesture: vi.fn(),
  ouvrirPdfBlob: vi.fn(),
  estBlobPdf: vi.fn(() => true),
  messageErreurBlob: vi.fn(async () => ''),
}))

import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import NoteDebitDialog from './NoteDebitDialog'

const FACTURE = { id: 11, reference: 'FAC-202607-0001' }

describe('NoteDebitDialog (WIR103)', () => {
  it('liste les notes de débit de la facture', async () => {
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} />)
    await waitFor(() =>
      expect(ventesApi.getNotesDebit).toHaveBeenCalledWith({ facture: 11 }))
    expect(await screen.findByText('ND-202607-0001')).toBeInTheDocument()
  })

  it('crée une note de débit puis l\'ajoute à la liste', async () => {
    const user = userEvent.setup()
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} />)
    await screen.findByText('ND-202607-0001')

    await user.click(screen.getByRole('button', { name: /Créer la note de débit/ }))
    await waitFor(() =>
      expect(ventesApi.creerNoteDebit).toHaveBeenCalledWith(11, { motif: '' }))
    expect(await screen.findByText('ND-202607-0002')).toBeInTheDocument()
  })

  it('télécharge le PDF d\'une note de débit', async () => {
    const user = userEvent.setup()
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} />)
    await screen.findByText('ND-202607-0001')

    await user.click(screen.getAllByRole('button', { name: /PDF/ })[0])
    await waitFor(() =>
      expect(ventesApi.telechargerNoteDebitPdf).toHaveBeenCalledWith(3))
    expect(openPdfBlob).toHaveBeenCalled()
  })
})
