import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WIR222 / XPUR9 — « Générer l'avoir » depuis un retour fournisseur VALIDÉ.
   L'action serveur (`retours-fournisseur/<id>/generer-avoir/`) existait sans
   aucun bouton : la traçabilité de l'avoir et la garde anti-double-avoir
   étaient inatteignables depuis l'écran.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getRetoursFournisseur: vi.fn(),
    getRetourFournisseur: vi.fn(),
    genererAvoirRetourFournisseur: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import { RetourDetail } from './RetoursFournisseur.jsx'

const retourValide = {
  id: 5, reference: 'RF-2026-08-0005', statut: 'valide',
  fournisseur_nom: 'JA Solar', motif: 'Panneaux fêlés',
  lignes: [{ id: 1, produit_nom: 'Panneau 550W', quantite: 2, motif: 'casse' }],
}

function wrap(node) {
  return render(<ThemeProvider>{node}</ThemeProvider>)
}

beforeEach(() => { vi.clearAllMocks() })

describe('WIR222 — générer l\'avoir depuis un retour', () => {
  it('un retour BROUILLON n\'expose pas l\'action', () => {
    wrap(<RetourDetail retour={{ ...retourValide, statut: 'brouillon' }} onClose={() => {}} />)
    expect(screen.queryByRole('button', { name: /Générer l'avoir/ })).toBeNull()
  })

  it('un retour validé produit l\'avoir lié avec ses montants pré-remplis', async () => {
    stockApi.genererAvoirRetourFournisseur.mockResolvedValue({
      data: { id: 9, reference: 'AVF-2026-08-0009', montant_ttc: '2400.00' },
    })
    const onAvoirGenere = vi.fn()
    wrap(<RetourDetail retour={retourValide} onClose={() => {}} onAvoirGenere={onAvoirGenere} />)

    fireEvent.click(screen.getByRole('button', { name: /Générer l'avoir/ }))

    await waitFor(() => expect(stockApi.genererAvoirRetourFournisseur)
      .toHaveBeenCalledWith(5))
    expect(await screen.findByText(/AVF-2026-08-0009/)).toBeInTheDocument()
    expect(onAvoirGenere).toHaveBeenCalled()
  })

  it('un second clic est refusé : le 400 serveur est affiché tel quel', async () => {
    stockApi.genererAvoirRetourFournisseur.mockRejectedValue({
      response: { status: 400, data: { detail: 'Ce retour a déjà un avoir.' } },
    })
    wrap(<RetourDetail retour={retourValide} onClose={() => {}} />)

    fireEvent.click(screen.getByRole('button', { name: /Générer l'avoir/ }))
    expect(await screen.findByText('Ce retour a déjà un avoir.')).toBeInTheDocument()
  })
})
