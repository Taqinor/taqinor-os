import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WR4 — « facturer une réception » (FG56) + PDF facture fournisseur (FG55).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    facturerReception: vi.fn(),
    confirmerReceptionFournisseur: vi.fn(),
    annulerReceptionFournisseur: vi.fn(),
    factureFournisseurPdf: vi.fn(),
    ajouterPaiementFournisseur: vi.fn(),
    receptionEtiquettes: vi.fn(),
  },
}))

vi.mock('../../api/comptaApi', () => ({
  default: {
    immobilisations: { depuisFactureFournisseur: vi.fn() },
  },
}))

// ZSTK13 — `useStockFlags` (utilisé par `ReceptionDetail`) lit le profil
// entreprise ; défaut True (lots/séries actives) = comportement inchangé.
vi.mock('../../api/parametresApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getProfile: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})

import stockApi from '../../api/stockApi'
import comptaApi from '../../api/comptaApi'
import { ReceptionDetail } from './ReceptionsFournisseur.jsx'
import { FactureDetail } from './FacturesFournisseur.jsx'

function wrap(node) {
  return render(<ThemeProvider>{node}</ThemeProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
  window.open = vi.fn(() => ({}))
})

describe('WR4 — facturer une réception (FG56)', () => {
  const reception = {
    id: 7, reference: 'REC-2026-07-0007', statut: 'confirme',
    bon_commande_reference: 'BCF-1', fournisseur_nom: 'JA Solar',
    date_reception: '2026-07-01',
    lignes: [{ id: 1, produit_nom: 'Panneau', quantite: 5 }],
  }

  it('affiche « Facturer cette réception » pour une réception confirmée', async () => {
    stockApi.facturerReception.mockResolvedValue({
      data: { id: 3, reference: 'FF-2026-07-0003', montant_ttc: '6000.00' },
    })
    wrap(<ReceptionDetail reception={reception} onClose={() => {}} onSaved={() => {}} />)
    const btn = screen.getByRole('button', { name: /Facturer cette réception/ })
    fireEvent.click(btn)
    await waitFor(() => { expect(stockApi.facturerReception).toHaveBeenCalledWith(7) })
    const status = await screen.findByRole('status')
    expect(status.textContent).toContain('FF-2026-07-0003')
  })

  it('ne montre PAS le bouton facturer pour un brouillon', () => {
    wrap(<ReceptionDetail reception={{ ...reception, statut: 'brouillon' }}
                          onClose={() => {}} onSaved={() => {}} />)
    expect(screen.queryByRole('button', { name: /Facturer cette réception/ })).toBeNull()
  })
})

describe('ZSTK6 — étiquettes lot/série sur une réception', () => {
  const receptionSansSerie = {
    id: 8, reference: 'REC-2026-07-0008', statut: 'confirme',
    lignes: [{ id: 1, produit_nom: 'Panneau', quantite: 5 }],
  }
  const receptionAvecSerie = {
    id: 9, reference: 'REC-2026-07-0009', statut: 'confirme',
    lignes: [{ id: 1, produit_nom: 'Onduleur', quantite: 2, numeros_serie: ['SN001', 'SN002'] }],
  }
  const receptionAvecLot = {
    id: 10, reference: 'REC-2026-07-0010', statut: 'confirme',
    lignes: [{ id: 1, produit_nom: 'Câble', quantite: 100, numero_lot: 'LOT-42' }],
  }

  it('sans numéro de série/lot : le bouton est absent', () => {
    wrap(<ReceptionDetail reception={receptionSansSerie} onClose={() => {}} onSaved={() => {}} />)
    expect(screen.queryByRole('button', { name: /Étiquettes lot\/série/ })).toBeNull()
  })

  it('avec des numéros de série : le bouton imprime les étiquettes', async () => {
    stockApi.receptionEtiquettes.mockResolvedValue({
      data: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    })
    wrap(<ReceptionDetail reception={receptionAvecSerie} onClose={() => {}} onSaved={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /Étiquettes lot\/série/ }))
    await waitFor(() => {
      expect(stockApi.receptionEtiquettes).toHaveBeenCalledWith(9)
      expect(window.open).toHaveBeenCalled()
    })
  })

  it('avec un lot renseigné : le bouton est aussi affiché', () => {
    wrap(<ReceptionDetail reception={receptionAvecLot} onClose={() => {}} onSaved={() => {}} />)
    expect(screen.getByRole('button', { name: /Étiquettes lot\/série/ })).toBeInTheDocument()
  })
})

describe('WR4 — PDF facture fournisseur (FG55)', () => {
  const facture = {
    id: 11, reference: 'FF-2026-07-0011', statut: 'a_payer',
    fournisseur_nom: 'JA Solar', montant_ttc: '6000', total_paye: '0',
    solde_du: '6000', paiements: [],
  }

  it('ouvre le PDF de la facture dans un nouvel onglet', async () => {
    stockApi.factureFournisseurPdf.mockResolvedValue({
      data: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    })
    wrap(<FactureDetail facture={facture} onClose={() => {}} onSaved={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    await waitFor(() => {
      expect(stockApi.factureFournisseurPdf).toHaveBeenCalledWith(11)
      expect(window.open).toHaveBeenCalled()
    })
  })

  it('affiche l\'erreur serveur (lue depuis le blob) si le PDF échoue', async () => {
    stockApi.factureFournisseurPdf.mockRejectedValue({
      response: {
        status: 403,
        data: new Blob([JSON.stringify({ detail: 'Réservé aux responsables.' })],
          { type: 'application/json' }),
      },
    })
    wrap(<FactureDetail facture={facture} onClose={() => {}} onSaved={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /PDF \(interne\)/ }))
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Réservé aux responsables.')
  })
})

describe('XACC33 — capitaliser une ligne de facture fournisseur (bouton « Immobiliser »)', () => {
  const facture = {
    id: 11, reference: 'FF-2026-07-0011', statut: 'a_payer',
    fournisseur_nom: 'JA Solar', montant_ttc: '6000', total_paye: '0',
    solde_du: '6000', paiements: [],
  }

  it('appelle depuisFactureFournisseur avec la ligne saisie', async () => {
    comptaApi.immobilisations.depuisFactureFournisseur.mockResolvedValue({ data: { id: 5 } })
    window.prompt = vi.fn(() => '42')
    wrap(<FactureDetail facture={facture} onClose={() => {}} onSaved={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /Immobiliser/ }))
    await waitFor(() => {
      expect(comptaApi.immobilisations.depuisFactureFournisseur).toHaveBeenCalledWith(
        expect.objectContaining({ facture_id: 11, ligne_id: 42 }))
    })
  })

  it('annule si aucun ligne_id n’est saisi', () => {
    window.prompt = vi.fn(() => null)
    wrap(<FactureDetail facture={facture} onClose={() => {}} onSaved={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /Immobiliser/ }))
    expect(comptaApi.immobilisations.depuisFactureFournisseur).not.toHaveBeenCalled()
  })
})
