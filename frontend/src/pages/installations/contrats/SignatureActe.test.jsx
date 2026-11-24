import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, documentContrat } from '../../../test/fixtures/contractSamples'

const { documentsApiMock } = vi.hoisted(() => ({
  documentsApiMock: { acte: vi.fn(), signerActe: vi.fn(), marquerActeSigne: vi.fn() },
}))
vi.mock('../../../api/documentsApi', () => ({ default: documentsApiMock }))
vi.mock('../../../features/installations/SignaturePad', () => ({
  default: ({ onChange }) => (
    <button type="button" onClick={() => onChange('data:image/png;base64,AAAA')}>
      Simuler un tracé
    </button>
  ),
}))

import SignatureActeDialog from './SignatureActeDialog'
import SignaturePapierDialog from './SignaturePapierDialog'

const ACTE = { id: 31, titre: 'Contrat d\'installation' }

beforeEach(() => {
  vi.clearAllMocks()
  documentsApiMock.acte.mockResolvedValue({ data: exempleContrat('documents', 'acte_contractuel') })
})
afterEach(() => cleanup())

describe('Signature d’un acte', () => {
  it('sur place : envoie exactement les clés de corps_signer', async () => {
    documentsApiMock.signerActe.mockResolvedValue({ data: {} })
    const onSigned = vi.fn()
    const user = userEvent.setup()
    render(<SignatureActeDialog open acte={ACTE} onOpenChange={vi.fn()} onSigned={onSigned} />)
    const nom = await screen.findByLabelText('Nom du signataire')
    await waitFor(() => expect(nom).toHaveValue('M. Youssef EL EXEMPLE'))
    expect(screen.getByLabelText('Lieu de signature')).toHaveValue('Bouskoura')
    expect(screen.getByRole('button', { name: /Enregistrer la signature/ })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Simuler un tracé' }))
    await user.click(screen.getByRole('button', { name: /Enregistrer la signature/ }))
    const corps = documentsApiMock.signerActe.mock.calls[0][1]
    expect(documentsApiMock.signerActe.mock.calls[0][0]).toBe(31)
    expect(Object.keys(corps).sort()).toEqual(
      Object.keys(documentContrat('documents', 'acte_contractuel').corps_signer).sort(),
    )
    expect(corps).toEqual({
      signature_client: 'data:image/png;base64,AAAA',
      signataire_nom: 'M. Youssef EL EXEMPLE',
      lieu: 'Bouskoura',
    })
    await waitFor(() => expect(onSigned).toHaveBeenCalled())
  })

  it('sur place : un refus serveur s’affiche en place', async () => {
    documentsApiMock.signerActe.mockRejectedValue({
      response: { data: exempleContrat('documents', 'acte_contractuel', 'exemple_409_deja_signe') },
    })
    const user = userEvent.setup()
    render(<SignatureActeDialog open acte={ACTE} onOpenChange={vi.fn()} onSigned={vi.fn()} />)
    await waitFor(() => expect(screen.getByLabelText('Nom du signataire')).toHaveValue('M. Youssef EL EXEMPLE'))
    await user.click(screen.getByRole('button', { name: 'Simuler un tracé' }))
    await user.click(screen.getByRole('button', { name: /Enregistrer la signature/ }))
    expect(await screen.findByText('Cet acte est déjà signé.')).toBeInTheDocument()
  })

  it('sur papier : envoie exactement les clés de corps_marquer_signe', async () => {
    documentsApiMock.marquerActeSigne.mockResolvedValue({ data: {} })
    const user = userEvent.setup()
    render(<SignaturePapierDialog open acte={ACTE} onOpenChange={vi.fn()} onDone={vi.fn()} />)
    await waitFor(() => expect(screen.getByLabelText('Nom du signataire')).toHaveValue('M. Youssef EL EXEMPLE'))
    const date = screen.getByLabelText('Date de signature')
    await user.clear(date)
    await user.type(date, '2026-11-24')
    await user.click(screen.getByRole('button', { name: 'Marquer signé' }))
    const corps = documentsApiMock.marquerActeSigne.mock.calls[0][1]
    expect(Object.keys(corps).sort()).toEqual(
      Object.keys(documentContrat('documents', 'acte_contractuel').corps_marquer_signe).sort(),
    )
    expect(corps.signe_le).toBe('2026-11-24')
  })
})
