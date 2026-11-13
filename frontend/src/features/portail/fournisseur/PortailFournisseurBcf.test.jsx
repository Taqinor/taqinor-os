import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* AERR128 (C-AERR-099) — « Mes bons de commande » du portail fournisseur :
   une relecture rejetée après la confirmation d'une date garde les commandes
   déjà listées (avis « pas à jour » + Réessayer) au lieu de « Commandes
   indisponibles ». Lignes alignées sur `MesBcfPortailFournisseurViewSet`
   (reference, date_commande, date_livraison_prevue, statut, statut_display,
   a_confirmer, lignes[produit_nom, quantite]). */

vi.mock('../../../api/portailApi', () => ({
  default: {
    fournisseur: { bonsCommande: { liste: vi.fn(), confirmer: vi.fn() } },
  },
}))

const toastSpy = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../../ui', async (orig) => {
  const m = await orig()
  return { ...m, toast: { ...m.toast, success: toastSpy.success, error: toastSpy.error } }
})

import portailApi from '../../../api/portailApi'
import PortailFournisseurBcf from './PortailFournisseurBcf.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const BCF = {
  id: 7, reference: 'BCF-2026-0031', date_commande: '2026-11-02',
  date_livraison_prevue: '2026-11-20', statut: 'envoye', statut_display: 'Envoyé',
  a_confirmer: true, date_confirmee_fournisseur: null, numero_confirmation_fournisseur: '',
  lignes: [{ produit_nom: 'Panneau 550 W', quantite: 24 }],
}

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><PortailFournisseurBcf /></ThemeProvider></MemoryRouter>,
  )
}

describe('PortailFournisseurBcf — AERR128', () => {
  it('relecture rejetée après confirmation : commandes gardées', async () => {
    portailApi.fournisseur.bonsCommande.liste
      .mockResolvedValueOnce({ data: { results: [BCF] } })
      .mockRejectedValueOnce({ response: { status: 502, data: {} } })
    portailApi.fournisseur.bonsCommande.confirmer.mockResolvedValue({ data: { id: 7 } })
    renderPage()
    await screen.findByText('BCF-2026-0031')
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer une date' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer cette date' }))
    await waitFor(() => expect(portailApi.fournisseur.bonsCommande.confirmer).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/Commandes pas à jour/)).toBeTruthy()
    expect(screen.getByText('BCF-2026-0031')).toBeTruthy()
    expect(screen.queryByText('Commandes indisponibles')).toBeNull()
    expect(toastSpy.success).toHaveBeenCalledTimes(1)
  })

  it('premier chargement rejeté : « Commandes indisponibles »', async () => {
    portailApi.fournisseur.bonsCommande.liste.mockRejectedValue({ response: { status: 502, data: {} } })
    renderPage()
    expect(await screen.findByText('Commandes indisponibles')).toBeTruthy()
  })
})
