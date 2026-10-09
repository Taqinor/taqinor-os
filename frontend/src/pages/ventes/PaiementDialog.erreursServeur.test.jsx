import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* AFAC61 — un refus 400 du serveur à l'encaissement s'affiche SOUS le champ
   Montant (message du serveur, saisie conservée), jamais un toast générique. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: {
    enregistrerPaiement: vi.fn(),
    arrondiCaisseFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import PaiementDialog from './PaiementDialog'

const FACTURE = {
  id: 7, reference: 'FAC-007', client_nom: 'ACME', montant_du: '1000.00',
  montant_paye: '0.00', total_ttc: '1000.00', statut: 'emise',
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PaiementDialog — AFAC61 : erreurs serveur sous le champ', () => {
  it('affiche le message `montant` du serveur sous Montant et garde la saisie', async () => {
    const MSG = 'Le montant ne peut pas avoir plus de 2 chiffres après la virgule.'
    ventesApi.enregistrerPaiement.mockRejectedValue({
      response: { status: 400, data: { montant: [MSG] } },
    })
    const user = userEvent.setup()
    render(<PaiementDialog facture={FACTURE} onOpenChange={() => {}} onSaved={() => {}} />)
    const champ = await screen.findByLabelText(/Montant/)
    await user.clear(champ)
    await user.type(champ, '100.505')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    expect(await screen.findByText(MSG)).toBeInTheDocument()
    expect(screen.getByLabelText(/Montant/)).toHaveValue(100.505)
  })

  it('une erreur `detail` sans champ s\'affiche en alerte', async () => {
    ventesApi.enregistrerPaiement.mockRejectedValue({
      response: { status: 400, data: { detail: 'Facture non encaissable.' } },
    })
    const user = userEvent.setup()
    render(<PaiementDialog facture={FACTURE} onOpenChange={() => {}} onSaved={() => {}} />)
    await screen.findByLabelText(/Montant/)
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Facture non encaissable.'))
  })
})
