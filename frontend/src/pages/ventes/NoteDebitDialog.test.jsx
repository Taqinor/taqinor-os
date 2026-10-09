import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* WIR103 + AFAC33 — note de débit : lister, créer (PARTIELLE : montant saisi,
   jamais toute la facture), annuler (admin), télécharger le PDF. Les réponses
   simulées de création viennent du contrat `note_debit_creation.json`. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const ICI = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(
  ICI, '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'facturation',
  'contract_samples', 'note_debit_creation.json'), 'utf8'))

vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdmin: () => true,
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getNotesDebit: vi.fn(() => Promise.resolve({
      data: [{ id: 3, reference: 'ND-202607-0001', total_ttc: '1200.00', statut: 'emise', annulee: false }],
    })),
    creerNoteDebit: vi.fn(),
    annulerNoteDebit: vi.fn(() => Promise.resolve({ data: { cree: true } })),
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

const FACTURE = { id: 11, reference: 'FAC-202607-0001', montant_du: '12000.00' }
const bouton = () => screen.getByRole('button', { name: /Créer la note de débit/ })

describe('NoteDebitDialog (WIR103 + AFAC33)', () => {
  it('liste les notes de débit de la facture', async () => {
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} />)
    await waitFor(() =>
      expect(ventesApi.getNotesDebit).toHaveBeenCalledWith({ facture: 11 }))
    expect(await screen.findByText('ND-202607-0001')).toBeInTheDocument()
  })

  it('refuse un motif seul : « Créer » reste inactif sans montant', async () => {
    const user = userEvent.setup()
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} />)
    await screen.findByText('ND-202607-0001')
    await user.type(screen.getByLabelText('Motif'), 'pénalité')
    expect(bouton()).toBeDisabled()
    expect(ventesApi.creerNoteDebit).not.toHaveBeenCalled()
  })

  it('crée une ND au montant saisi', async () => {
    ventesApi.creerNoteDebit.mockResolvedValue({ data: CONTRAT.exemple })
    const onChanged = vi.fn()
    const user = userEvent.setup()
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} onChanged={onChanged} />)
    await screen.findByText('ND-202607-0001')

    await user.type(screen.getByLabelText('Motif'), 'pénalité')
    await user.type(screen.getByLabelText(/Montant HT/), '500')
    await user.click(bouton())
    await waitFor(() =>
      expect(ventesApi.creerNoteDebit).toHaveBeenCalledWith(
        11, { motif: 'pénalité', montant: '500', taux_tva: '20' }))
    expect(await screen.findByText(CONTRAT.exemple.reference)).toBeInTheDocument()
    expect(onChanged).toHaveBeenCalled()
  })

  it('affiche le message serveur sous le champ', async () => {
    ventesApi.creerNoteDebit.mockRejectedValue({
      response: { data: { detail: 'Saisissez les lignes ou le montant de la note de débit' } },
    })
    const user = userEvent.setup()
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} />)
    await screen.findByText('ND-202607-0001')
    await user.type(screen.getByLabelText(/Montant HT/), '10')
    await user.click(bouton())
    expect(await screen.findByRole('alert')).toHaveTextContent('Saisissez les lignes ou le montant')
  })

  it('annule une ND (admin, avec confirmation)', async () => {
    const onChanged = vi.fn()
    const user = userEvent.setup()
    render(<NoteDebitDialog facture={FACTURE} open onOpenChange={() => {}} onChanged={onChanged} />)
    await screen.findByText('ND-202607-0001')

    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    await user.click(await screen.findByRole('button', { name: 'Annuler la note de débit' }))
    await waitFor(() => expect(ventesApi.annulerNoteDebit).toHaveBeenCalledWith(3))
    expect(await screen.findByText('Annulée')).toBeInTheDocument()
    expect(onChanged).toHaveBeenCalled()
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
