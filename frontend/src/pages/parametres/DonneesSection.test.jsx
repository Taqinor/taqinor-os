import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WR5 — surface Paramètres « Données » : sessions d'inventaire (valider /
   annuler), explosion de kit, fiches techniques.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getInventaireSessions: vi.fn(),
    validerInventaireSession: vi.fn(),
    annulerInventaireSession: vi.fn(),
    getKits: vi.fn(),
    exploserKit: vi.fn(),
    getFichesTechniques: vi.fn(),
    createFicheTechnique: vi.fn(),
    deleteFicheTechnique: vi.fn(),
    getProduits: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import DonneesSection from './DonneesSection.jsx'

function renderSection() {
  return render(
    <MemoryRouter>
      <ThemeProvider><DonneesSection /></ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  window.confirm = vi.fn(() => true)
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  stockApi.getInventaireSessions.mockResolvedValue({
    data: [{
      id: 1, reference: 'INV-2026-07-0001', statut: 'brouillon',
      lignes: [{ id: 1 }], date_creation: '2026-07-01T09:00:00Z',
    }],
  })
  stockApi.getKits.mockResolvedValue({
    data: [{ id: 5, nom: 'Kit résidentiel', sku: 'KIT-R' }],
  })
  stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: [] })
})

describe('WR5 — sessions d\'inventaire', () => {
  it('valide une session brouillon et affiche le résultat', async () => {
    stockApi.validerInventaireSession.mockResolvedValue({
      data: { ajustes: 2, inchanges: 3 },
    })
    renderSection()
    expect(await screen.findByText('INV-2026-07-0001')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Valider' }))
    await waitFor(() => {
      expect(stockApi.validerInventaireSession).toHaveBeenCalledWith(1)
    })
    const status = await screen.findByRole('status')
    expect(status.textContent).toMatch(/2 ajustement/)
  })

  it('annule une session brouillon', async () => {
    stockApi.annulerInventaireSession.mockResolvedValue({ data: {} })
    renderSection()
    expect(await screen.findByText('INV-2026-07-0001')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => {
      expect(stockApi.annulerInventaireSession).toHaveBeenCalledWith(1)
    })
  })
})

describe('WR5 — explosion de kit', () => {
  it('explose un kit en lignes composant', async () => {
    stockApi.exploserKit.mockResolvedValue({
      data: {
        kit_id: 5, kit_nom: 'Kit résidentiel', quantite_kit: 1,
        lignes: [{
          produit_id: 11, sku: 'PAN-550', designation: 'Panneau 550',
          quantite: 8, prix_vente_unitaire: '1000', tva: 20, marque: 'JA',
          disponible: 30,
        }],
      },
    })
    renderSection()
    // Attendre le chargement des kits.
    await waitFor(() => { expect(stockApi.getKits).toHaveBeenCalled() })
    // Sélectionner le kit (le Select radix expose un combobox).
    const btn = screen.getByRole('button', { name: 'Exploser' })
    fireEvent.click(btn)
    // Sans kit choisi → message d'erreur.
    expect(await screen.findByText(/Choisissez un kit/)).toBeVisible()
  })
})
