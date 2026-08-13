import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT121 — « Payer en ligne » depuis une facture (core.PaymentTransaction).
   Le test verrouille le contrat de la tâche : la demande est créée, et l'écran
   affiche SOIT le lien de paiement SOIT « prestataire non configuré » —
   jamais une erreur brute. */

vi.mock('../../api/axios', () => ({ default: { post: vi.fn() } }))

import api from '../../api/axios'
import PaiementEnLigneDialog from './PaiementEnLigneDialog'

const FACTURE = { id: 12, reference: 'FAC-0012', montant_du: '4500.00' }

const renderDialog = () => render(
  <PaiementEnLigneDialog facture={FACTURE} open onOpenChange={() => {}} />,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('PaiementEnLigneDialog (PACT121)', () => {
  it('crée la transaction et affiche le lien de paiement du prestataire', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({
      data: {
        id: 5, statut: 'en_attente', redirect_url: 'https://psp.example/pay/5',
        detail: {},
      },
    })
    renderDialog()
    await user.click(screen.getByRole('button', { name: /Créer la demande de paiement/ }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/core/paiements-en-ligne/',
      expect.objectContaining({ montant: '4500.00', devise: 'MAD' })))
    // `company` n'est JAMAIS envoyée depuis le client (imposée serveur).
    expect(api.post.mock.calls[0][1]).not.toHaveProperty('company')
    const lien = await screen.findByRole('link', { name: /Lien de paiement/ })
    expect(lien).toHaveAttribute('href', 'https://psp.example/pay/5')
  })

  it('affiche « non configuré » — jamais une erreur brute — sans compte marchand', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({
      data: {
        id: 6, statut: 'initie', redirect_url: '',
        detail: { detail: 'Connecteur cmi non configuré.' },
      },
    })
    renderDialog()
    await user.click(screen.getByRole('button', { name: /Créer la demande de paiement/ }))

    expect(await screen.findByText('Connecteur cmi non configuré.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Lien de paiement/ })).not.toBeInTheDocument()
  })

  it('traduit un échec réseau en message clair, sans détail technique', async () => {
    const user = userEvent.setup()
    api.post.mockRejectedValue(new Error('Request failed with status code 500'))
    renderDialog()
    await user.click(screen.getByRole('button', { name: /Créer la demande de paiement/ }))

    const message = await screen.findByRole('status')
    expect(message).toHaveTextContent(/n'a pas pu être initié/)
    expect(message).not.toHaveTextContent(/500/)
  })

  it('actualise le statut de la transaction déjà créée', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValueOnce({
      data: { id: 7, statut: 'en_attente', redirect_url: 'https://psp.example/pay/7', detail: {} },
    })
    renderDialog()
    await user.click(screen.getByRole('button', { name: /Créer la demande de paiement/ }))
    await screen.findByRole('link', { name: /Lien de paiement/ })

    api.post.mockResolvedValueOnce({
      data: { id: 7, statut: 'paye', redirect_url: 'https://psp.example/pay/7', detail: {} },
    })
    await user.click(screen.getByRole('button', { name: /Actualiser le statut/ }))

    await waitFor(() => expect(api.post)
      .toHaveBeenCalledWith('/core/paiements-en-ligne/7/rafraichir/'))
    expect(await screen.findByText('Payée')).toBeInTheDocument()
  })
})
