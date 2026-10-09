// ACHT59 — re-signature motivée d'un chantier déjà signé. Faux serveur en
// mémoire qui applique la règle réelle (409 sans `motif_override_signature`
// si déjà signé, `views/installation.py:795-823`), puis relecture.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { serveur } = vi.hoisted(() => ({
  serveur: { row: null, bodies: [], force: null },
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    signerClientChantier: (id, body) => {
      serveur.bodies.push(body)
      if (serveur.force) return Promise.reject(serveur.force)
      if (serveur.row.signe_le && !body.motif_override_signature) {
        return Promise.reject({ response: { status: 409, data: {
          detail: 'Chantier déjà signé : indiquez le motif de la re-signature.',
        } } })
      }
      serveur.row.signature_client = body.signature_client
      serveur.row.signataire_nom = body.signataire_nom
      serveur.row.signe_le = '2026-10-09T10:00:00Z'
      return Promise.resolve({ data: { ...serveur.row } })
    },
  },
}))
vi.mock('../../features/installations/SignaturePad', () => ({
  default: ({ onChange }) => (
    <button type="button" onClick={() => onChange('data:image/png;base64,NEW')}>Tracer</button>
  ),
}))
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import SignatureLivraisonDialog from './SignatureLivraisonDialog'
import { toast } from '../../ui'

const rendre = (row) => render(
  <SignatureLivraisonDialog open installation={{ ...row }}
    onOpenChange={vi.fn()} onSigned={vi.fn()} />,
)

beforeEach(() => { serveur.bodies = []; serveur.force = null; vi.clearAllMocks() })
afterEach(() => cleanup())

describe('SignatureLivraisonDialog — ACHT59 motif de re-signature', () => {
  it('chantier non signé : aucun champ motif, signature enregistrée', async () => {
    serveur.row = { id: 1, signe_le: null, signature_client: null }
    const user = userEvent.setup()
    rendre(serveur.row)
    expect(screen.queryByLabelText('Motif de la re-signature')).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Tracer' }))
    await user.click(screen.getByRole('button', { name: /enregistrer la signature/i }))
    await waitFor(() => expect(serveur.row.signature_client).toBe('data:image/png;base64,NEW'))
    expect(serveur.bodies[0]).not.toHaveProperty('motif_override_signature')
  })

  it('chantier signé : Enregistrer impossible sans motif, puis re-signature avec motif', async () => {
    serveur.row = {
      id: 2, signe_le: '2026-01-01T10:00:00Z',
      signature_client: 'data:image/png;base64,OLD', signataire_nom: 'Ancien',
    }
    const user = userEvent.setup()
    rendre(serveur.row)
    await user.click(screen.getByRole('button', { name: 'Tracer' }))
    expect(screen.getByText('Motif obligatoire')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /enregistrer la signature/i })).toBeDisabled()
    expect(serveur.row.signature_client).toBe('data:image/png;base64,OLD')

    await user.type(screen.getByLabelText('Motif de la re-signature'), 'Erreur de signataire')
    expect(screen.getByText(/la remplace/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /enregistrer la signature/i }))
    await waitFor(() => expect(serveur.row.signature_client).toBe('data:image/png;base64,NEW'))
    expect(serveur.bodies[0].motif_override_signature).toBe('Erreur de signataire')
  })

  it('un refus serveur sur le motif s’affiche sans nom de champ technique', async () => {
    serveur.row = { id: 3, signe_le: '2026-01-01T10:00:00Z', signature_client: 'OLD' }
    serveur.force = { response: { status: 409, data: {
      motif_override_signature: ['Motif invalide.'] } } }
    const user = userEvent.setup()
    rendre(serveur.row)
    await user.click(screen.getByRole('button', { name: 'Tracer' }))
    await user.type(screen.getByLabelText('Motif de la re-signature'), 'x')
    await user.click(screen.getByRole('button', { name: /enregistrer la signature/i }))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Motif invalide.'))
  })
})
