import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WIR222/XPUR9 — un retour VALIDÉ ne pouvait jamais générer son avoir fournisseur
   depuis l'écran (aucun bouton n'appelait `generer-avoir`, traçabilité et garde
   anti-double-avoir perdues). « Générer l'avoir » n'apparaît que sur un retour
   validé, jamais deux fois de suite dans la même session (400 serveur affiché
   tel quel au-delà).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    genererAvoirDepuisRetour: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import { RetourDetail } from './RetoursFournisseur.jsx'

function wrap(node) {
  return render(<ThemeProvider>{node}</ThemeProvider>)
}

beforeEach(() => { vi.clearAllMocks() })

const retourValide = {
  id: 5, reference: 'RF-2026-0005', statut: 'valide', fournisseur_nom: 'JA Solar',
  date_creation: '2026-07-01T10:00:00Z',
  lignes: [{ id: 1, produit_nom: 'Module 550', quantite: 2, motif: 'cassé' }],
}

describe('WIR222 — « Générer l\'avoir » sur un retour validé', () => {
  it('affiche le bouton sur un retour validé', () => {
    wrap(<RetourDetail retour={retourValide} onClose={() => {}} />)
    expect(screen.getByRole('button', { name: /Générer l'avoir/ })).toBeInTheDocument()
  })

  it('absent sur un retour brouillon ou annulé', () => {
    wrap(<RetourDetail retour={{ ...retourValide, statut: 'brouillon' }} onClose={() => {}} />)
    expect(screen.queryByRole('button', { name: /Générer l'avoir/ })).toBeNull()
  })

  it('appelle genererAvoirDepuisRetour(id), affiche la confirmation et masque le bouton (anti-double-avoir)', async () => {
    stockApi.genererAvoirDepuisRetour.mockResolvedValue({
      data: { id: 9, reference: 'AVF-2026-0009', montant_ttc: '1200.00' },
    })
    const onAvoirGenere = vi.fn()
    wrap(<RetourDetail retour={retourValide} onClose={() => {}} onAvoirGenere={onAvoirGenere} />)

    fireEvent.click(screen.getByRole('button', { name: /Générer l'avoir/ }))
    await waitFor(() => expect(stockApi.genererAvoirDepuisRetour).toHaveBeenCalledWith(5))
    expect(await screen.findByText(/AVF-2026-0009/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Générer l'avoir/ })).toBeNull()
    expect(onAvoirGenere).toHaveBeenCalledWith({ id: 9, reference: 'AVF-2026-0009', montant_ttc: '1200.00' })
  })

  it('un second retour déjà avoiré (400 serveur) affiche le message tel quel', async () => {
    stockApi.genererAvoirDepuisRetour.mockRejectedValue({
      response: { data: { detail: 'Ce retour a déjà un avoir associé.' } },
    })
    wrap(<RetourDetail retour={retourValide} onClose={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer l'avoir/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ce retour a déjà un avoir associé.')
  })
})
