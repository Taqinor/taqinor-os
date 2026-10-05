import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CONTRAT from '../../../../backend/django_core/apps/ventes/contract_samples/devis_facturer_complet.json'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: { facturerComplet: vi.fn(), telechargerPdfFacture: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import FacturerDevisDialog from './FacturerDevisDialog'

const DEVIS = { id: 7, reference: 'DEV-2026-10-0003', client_nom: 'Mme Alaoui', total_ttc: '150000.00' }

beforeEach(() => {
  ventesApi.facturerComplet.mockResolvedValue({ data: CONTRAT.exemple })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const saisir = async (user, i, v) => {
  const champ = screen.getByLabelText(`Montant paiement ${i}`)
  await user.clear(champ)
  await user.type(champ, v)
}

describe('FacturerDevisDialog', () => {
  it('calcule le reste à payer en direct', async () => {
    const user = userEvent.setup()
    render(<FacturerDevisDialog devis={DEVIS} onOpenChange={() => {}} />)
    await saisir(user, 1, '45000')
    await saisir(user, 2, '45000')
    await saisir(user, 3, '45000')
    expect(screen.getByTestId('facturer-reste').textContent.replace(/\s/g, ''))
      .toMatch(/15.?000/)
  })

  it('bloque un trop-perçu', async () => {
    const user = userEvent.setup()
    render(<FacturerDevisDialog devis={DEVIS} onOpenChange={() => {}} />)
    await saisir(user, 1, '200000')
    expect(screen.getByRole('alert').textContent).toMatch(/dépasse/)
    expect(screen.getByRole('button', { name: 'Créer la facture' }).disabled).toBe(true)
  })

  it('poste le bon corps et appelle onDone', async () => {
    const user = userEvent.setup()
    const onDone = vi.fn()
    render(<FacturerDevisDialog devis={DEVIS} onOpenChange={() => {}} onDone={onDone} />)
    await saisir(user, 1, '45000')
    await user.type(screen.getByLabelText('Référence paiement 1'), 'VIR-0812')
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    await waitFor(() => expect(ventesApi.facturerComplet).toHaveBeenCalled())
    const [id, body] = ventesApi.facturerComplet.mock.calls[0]
    expect(id).toBe(7)
    expect(body.paiements).toHaveLength(1)
    expect(body.paiements[0]).toMatchObject({
      montant: '45000', mode_paiement: 'virement', reference: 'VIR-0812',
    })
    expect(body.paiements[0].date_paiement).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    await waitFor(() => expect(onDone).toHaveBeenCalledWith(CONTRAT.exemple))
  })

  it('affiche le detail français du 400', async () => {
    ventesApi.facturerComplet.mockRejectedValue({
      response: { data: { detail: 'Ce devis porte déjà une facture active.' } },
    })
    const user = userEvent.setup()
    render(<FacturerDevisDialog devis={DEVIS} onOpenChange={() => {}} />)
    await user.click(screen.getByRole('button', { name: 'Créer la facture' }))
    expect(await screen.findByText('Ce devis porte déjà une facture active.')).toBeTruthy()
  })
})
