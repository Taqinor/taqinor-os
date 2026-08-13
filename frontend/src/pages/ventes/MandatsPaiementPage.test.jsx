import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT43 — vue interne des mandats de paiement tokenisés.
   Le test verrouille les deux garanties de la tâche :
     1. AUCUN champ de saisie de donnée de carte n'existe sur l'écran (aucun
        `<input>` texte/nombre : la tokenisation se fait hors ERP) ;
     2. une révocation appelle l'endpoint dédié et le mandat repasse
        visiblement en « Révoqué » / encaissement manuel. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({
    confirm: () => Promise.resolve(true),
    confirmDelete: () => Promise.resolve(true),
  }),
}))

import api from '../../api/axios'
import MandatsPaiementPage from './MandatsPaiementPage'

const ACTIF = {
  id: 7, client: 42, client_nom: 'ACME SARL', provider: 'cmi',
  derniers_chiffres: '4242', expiration_mois: '12/2027', statut: 'actif',
  consentement_horodate: '2026-01-05T10:00:00Z',
}
const REVOQUE = { ...ACTIF, statut: 'revoque' }

afterEach(() => { cleanup(); vi.clearAllMocks() })
beforeEach(() => {
  api.get.mockResolvedValue({ data: [ACTIF] })
  api.post.mockResolvedValue({ data: REVOQUE })
})

describe('MandatsPaiementPage (PACT43)', () => {
  it('liste les mandats sans jamais demander de donnée de carte', async () => {
    const { container } = render(<MandatsPaiementPage />)
    await waitFor(() => expect(api.get)
      .toHaveBeenCalledWith('/ventes/mandats-paiement/'))
    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()
    // Seuls les 4 derniers chiffres — jamais un numéro complet.
    expect(screen.getByText('•••• 4242')).toBeInTheDocument()
    // Zéro champ de saisie : rien de carte ne peut être tapé dans l'ERP.
    expect(container.querySelectorAll('input')).toHaveLength(0)
    expect(container.querySelectorAll('form')).toHaveLength(0)
  })

  it('révoque un mandat : le client repasse en encaissement manuel', async () => {
    const user = userEvent.setup()
    render(<MandatsPaiementPage />)
    const bouton = await screen.findByRole('button', { name: 'Révoquer' })

    api.get.mockResolvedValue({ data: [REVOQUE] })
    await user.click(bouton)

    await waitFor(() => expect(api.post)
      .toHaveBeenCalledWith('/ventes/mandats-paiement/7/revoquer/'))
    expect(await screen.findByText('Révoqué')).toBeInTheDocument()
    expect(await screen.findByText('Encaissement manuel')).toBeInTheDocument()
  })

  it('filtre sur les mandats révoqués', async () => {
    const user = userEvent.setup()
    api.get.mockResolvedValue({ data: [ACTIF] })
    render(<MandatsPaiementPage />)
    await screen.findByText('ACME SARL')

    await user.click(screen.getByRole('radio', { name: 'Révoqués' }))
    expect(screen.queryByText('ACME SARL')).not.toBeInTheDocument()
    expect(screen.getByText('Aucun mandat')).toBeInTheDocument()
  })
})
