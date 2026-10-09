import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

/* AFAC65 — le dialogue relit la facture : ouvert depuis Relances avec la ligne
   `/relances/` (sans montant_paye ni paiements), il affiche les vrais Payé /
   Dû et le paiement existant (forme réelle FactureSerializer). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const LIGNE_RELANCES = {
  id: 9, reference: 'FAC-009', client_id: 42, client_nom: 'ACME', montant_du: 3000,
}
const FACTURE_SERVEUR = {
  id: 9, reference: 'FAC-009', client_nom: 'ACME', total_ttc: '3000.00',
  montant_paye: '1000.00', montant_du: '2000.00', statut: 'partiellement_payee',
  paiements: [{ id: 1, montant: '1000.00', date_paiement: '2026-08-01', mode: 'virement', reference: 'VIR-1' }],
}

vi.mock('../../api/ventesApi', () => ({
  default: {
    getFacture: vi.fn(),
    enregistrerPaiement: vi.fn(),
    arrondiCaisseFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import PaiementDialog from './PaiementDialog'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PaiementDialog — AFAC65 : instantané relu', () => {
  it('depuis Relances : vrais Payé/Dû, paiement listé, montant = dû de la facture', async () => {
    ventesApi.getFacture.mockResolvedValue({ data: FACTURE_SERVEUR })
    render(<PaiementDialog facture={LIGNE_RELANCES} onOpenChange={() => {}} onSaved={() => {}} />)

    await waitFor(() => expect(ventesApi.getFacture).toHaveBeenCalledWith(9))
    expect(await screen.findByText(/Payé 1\s?000,00/)).toBeInTheDocument()
    expect((await screen.findAllByText(/VIR-1/)).length).toBeGreaterThan(0)
    expect(screen.queryByText('Aucun paiement enregistré.')).toBeNull()
    await waitFor(() => expect(screen.getByLabelText(/Montant/)).toHaveValue(2000))
  })

  it('relit la facture après un paiement enregistré', async () => {
    ventesApi.getFacture.mockResolvedValue({ data: FACTURE_SERVEUR })
    ventesApi.enregistrerPaiement.mockResolvedValue({ data: { statut: 'partiellement_payee' } })
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    render(<PaiementDialog facture={LIGNE_RELANCES} onOpenChange={() => {}} onSaved={() => {}} />)
    await screen.findByText(/Payé 1\s?000,00/)
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(ventesApi.getFacture).toHaveBeenCalledTimes(2))
  })
})
