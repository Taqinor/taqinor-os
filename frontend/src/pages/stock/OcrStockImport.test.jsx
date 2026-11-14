import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ACNC29 (C-ACNC-013) — « Réessayer les échecs » de l'import OCR en mode BCF
   reprend à l'étape échouée : le BCF mémorisé est RELU, jamais recréé ; reçu
   côté serveur, il n'est pas reçu une seconde fois. Seule l'API est simulée.
   ========================================================================== */

vi.mock('../../lib/monitoring', () => ({ captureException: () => {}, initMonitoring: () => {} }))
vi.mock('../../features/stock/useVoitPrixAchat', () => ({
  usePermissionAchats: () => true,
  useVoitPrixAchat: () => true,
}))
vi.mock('../../features/stock/store/stockSlice', () => ({
  fetchProduits: () => ({ type: 'noop/produits' }),
  fetchFournisseurs: () => ({ type: 'noop/fournisseurs' }),
  fetchCategories: () => ({ type: 'noop/categories' }),
  fetchMouvements: () => ({ type: 'noop/mouvements' }),
}))
vi.mock('../../features/ia/store/iaSlice', () => ({
  processOcrStockDocument: () => ({ type: 'noop/ocr' }),
  clearStockOcrResult: () => ({ type: 'noop/clear' }),
}))
vi.mock('../../api/stockApi', () => ({
  default: {
    createBonCommandeFournisseur: vi.fn(),
    envoyerBcf: vi.fn(() => Promise.resolve({ data: {} })),
    recevoirBcf: vi.fn(),
    getBonCommandeFournisseur: vi.fn(),
    patchProduit: vi.fn(() => Promise.resolve({ data: {} })),
    createMouvement: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import OcrStockImport from './OcrStockImport.jsx'

const PRODUIT = { id: 5, nom: 'Onduleur 5 kW', sku: 'OND5', prix_achat: '1000', fournisseur: 1 }

function monter() {
  const store = configureStore({
    reducer: {
      auth: (s = { role: 'admin', role_nom: null, permissions: [] }) => s,
      stock: (s = { produits: [PRODUIT], fournisseurs: [{ id: 1, nom: 'Grossiste' }], categories: [] }) => s,
      ia: (s = {
        stockOcrResult: { fournisseur: 'Grossiste', reference_document: 'BL-1', mouvement_suggere: 'entree',
          lignes: [{ reference: 'OND5', nom: 'Onduleur 5 kW', quantite: 2, prix_unitaire_ht: 1000 }] },
        stockOcrDocType: 'bon_livraison', stockOcrLoading: false, stockOcrError: null,
      }) => s,
    },
  })
  return render(
    <Provider store={store}><MemoryRouter><ThemeProvider><OcrStockImport /></ThemeProvider></MemoryRouter></Provider>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('ACNC29 — import OCR en mode BCF : réessai sans recréer', () => {
  it('réception expirée côté écran mais faite côté serveur : le réessai relit le BCF, ni create ni recevoir', async () => {
    const bcf = { id: 31, reference: 'BCF-31', statut: 'brouillon', lignes: [{ id: 8, quantite: 2 }] }
    stockApi.createBonCommandeFournisseur.mockResolvedValue({ data: bcf })
    stockApi.recevoirBcf.mockRejectedValueOnce(new Error('timeout of 20000ms exceeded'))
    stockApi.getBonCommandeFournisseur.mockResolvedValue({ data: { ...bcf, statut: 'recu' } })
    monter()
    const option = (await screen.findByText('Créer un bon de commande fournisseur reçu')).closest('label')
    fireEvent.click(within(option).getByRole('checkbox'))
    fireEvent.click(await screen.findByRole('button', { name: /Créer le bon de commande reçu/ }))
    const reessayer = await screen.findByRole('button', { name: /Réessayer les échecs/ })
    expect(stockApi.createBonCommandeFournisseur).toHaveBeenCalledTimes(1)
    expect(stockApi.recevoirBcf).toHaveBeenCalledTimes(1)
    fireEvent.click(reessayer)
    await waitFor(() => expect(stockApi.getBonCommandeFournisseur).toHaveBeenCalledWith(31))
    expect(await screen.findByText(/Reçu via le bon de commande BCF-31/)).toBeInTheDocument()
    expect(stockApi.createBonCommandeFournisseur).toHaveBeenCalledTimes(1)
    expect(stockApi.recevoirBcf).toHaveBeenCalledTimes(1)
    expect(stockApi.envoyerBcf).toHaveBeenCalledTimes(1)
  })
})
