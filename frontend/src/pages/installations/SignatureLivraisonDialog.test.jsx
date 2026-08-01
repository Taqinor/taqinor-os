// NTMOB16 — signature client tracée sur le bon de livraison chantier.
// SignaturePad.jsx (canvas Pointer Events) est déjà un composant établi, non
// testé nulle part ailleurs dans le repo (SignatureClientPanel.jsx, son
// premier usage FG69/VX106, n'a pas non plus de test) — ce test le mocke
// pour rester focalisé sur le câblage propre à CE dialog (payload API,
// fermeture, gestion d'erreur), même patron que ChantierChecklist.ntmob11.test.jsx.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { installationsApiMock } = vi.hoisted(() => ({
  installationsApiMock: { signerClientChantier: vi.fn() },
}))
vi.mock('../../api/installationsApi', () => ({ default: installationsApiMock }))

vi.mock('../../features/logistique/SignaturePad', () => ({
  default: ({ onChange }) => (
    <button type="button" onClick={() => onChange('data:image/png;base64,AAAA')}>
      Simuler un tracé
    </button>
  ),
}))

import SignatureLivraisonDialog from './SignatureLivraisonDialog'

const INSTALLATION = { id: 42, reference: 'CH-2026-001', signe_le: null, signataire_nom: '' }

beforeEach(() => {
  vi.clearAllMocks()
  installationsApiMock.signerClientChantier.mockResolvedValue({
    data: { id: 42, signature_client: 'data:image/png;base64,AAAA' },
  })
})
afterEach(() => cleanup())

describe('SignatureLivraisonDialog (NTMOB16)', () => {
  it('le bouton « Enregistrer » reste désactivé tant qu’aucun tracé n’a été fait', () => {
    render(
      <SignatureLivraisonDialog open installation={INSTALLATION}
        onOpenChange={vi.fn()} onSigned={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: /enregistrer la signature/i })).toBeDisabled()
    expect(installationsApiMock.signerClientChantier).not.toHaveBeenCalled()
  })

  it('trace + enregistre envoie le data-URL PNG et le nom saisi', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const onSigned = vi.fn()
    render(
      <SignatureLivraisonDialog open installation={INSTALLATION}
        onOpenChange={onOpenChange} onSigned={onSigned} />,
    )

    await user.type(screen.getByPlaceholderText(/nom du signataire/i), 'Karim Bennani')
    await user.click(screen.getByRole('button', { name: 'Simuler un tracé' }))
    await user.click(screen.getByRole('button', { name: /enregistrer la signature/i }))

    await waitFor(() =>
      expect(installationsApiMock.signerClientChantier).toHaveBeenCalledTimes(1))
    expect(installationsApiMock.signerClientChantier).toHaveBeenCalledWith(42, {
      signature_client: 'data:image/png;base64,AAAA',
      signataire_nom: 'Karim Bennani',
    })
    expect(onSigned).toHaveBeenCalledTimes(1)
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('un chantier déjà signé affiche un rappel avant de re-signer', () => {
    render(
      <SignatureLivraisonDialog open
        installation={{ ...INSTALLATION, signe_le: '2026-01-01T10:00:00Z', signataire_nom: 'Karim Bennani' }}
        onOpenChange={vi.fn()} onSigned={vi.fn()} />,
    )
    expect(screen.getByText(/déjà signé par karim bennani/i)).toBeInTheDocument()
  })

  it('un échec réseau n’efface pas le tracé et ne ferme pas le dialog', async () => {
    installationsApiMock.signerClientChantier.mockRejectedValueOnce({
      response: { data: { detail: 'Erreur serveur.' } },
    })
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    render(
      <SignatureLivraisonDialog open installation={INSTALLATION}
        onOpenChange={onOpenChange} onSigned={vi.fn()} />,
    )

    await user.click(screen.getByRole('button', { name: 'Simuler un tracé' }))
    await user.click(screen.getByRole('button', { name: /enregistrer la signature/i }))

    await waitFor(() =>
      expect(installationsApiMock.signerClientChantier).toHaveBeenCalledTimes(1))
    expect(onOpenChange).not.toHaveBeenCalled()
  })
})
