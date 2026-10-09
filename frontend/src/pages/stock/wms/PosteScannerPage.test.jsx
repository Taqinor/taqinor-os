import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK216 — « Poste scanner » : codes résolus, mouvement scanné, retour
   fournisseur. Les réponses des routes scanner viennent du contrat committé
   `wms_casiers.json` ; seul axios est mocké. La ventilation et l'historique
   (routes produit existantes, hors contrat ASTK160) sont décrits à la main
   d'après `stock_breakdown` / MouvementStockSerializer.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import PosteScannerPage from './PosteScannerPage'

const R = documentContrat('stock', 'wms_casiers').routes
const SC = R.scanner_resoudre
const MV = R.scanner_mouvement
const RET = R.scanner_retour_fournisseur

const VENTILATION = [
  { emplacement_id: 3, emplacement_nom: 'Dépôt principal', is_principal: true, quantite: 240 },
  { emplacement_id: 7, emplacement_nom: 'Camionnette 1', is_principal: false, quantite: 37 },
]
const HISTORIQUE = { count: 1, results: [{ id: 1203, type_mouvement: 'transfert', quantite: 37, reference: 'SCAN', date: '2026-10-06T09:20:00Z' }] }

function brancher() {
  api.get.mockImplementation((url, cfg) => {
    if (url === '/stock/scanner/resoudre/') {
      const code = cfg?.params?.code
      if (code === 'MIC-001') return Promise.resolve({ data: SC.exemple_produit })
      if (code === 'P-01-01') return Promise.resolve({ data: SC.exemple })
      return Promise.reject({ response: { status: 404, data: SC.exemple_erreur_404 } })
    }
    if (url === '/stock/scanner/retour-fournisseur/') return Promise.resolve({ data: RET.exemple })
    if (url.includes('/emplacements/')) return Promise.resolve({ data: VENTILATION })
    if (url === '/stock/mouvements/') return Promise.resolve({ data: HISTORIQUE })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><PosteScannerPage /></MemoryRouter>)

async function scanner(code) {
  fireEvent.change(screen.getByLabelText('Code scanné'), { target: { value: code } })
  fireEvent.click(screen.getByRole('button', { name: /Résoudre/i }))
}

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK216 — PosteScannerPage', () => {
  it('résout un code puis pose le mouvement', async () => {
    api.post.mockResolvedValue({ data: MV.exemple })
    monter()
    await scanner('MIC-001')
    expect(await screen.findByText(/Micro-onduleur/)).toBeInTheDocument()
    await scanner('P-01-01')
    fireEvent.click(await screen.findByRole('button', { name: /Utiliser comme destination/i }))
    fireEvent.change(screen.getByLabelText('Type de mouvement'), { target: { value: 'entree' } })
    fireEvent.change(screen.getByLabelText('Quantité'), { target: { value: '37' } })
    fireEvent.click(screen.getByRole('button', { name: /Valider le mouvement/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/scanner/mouvement/', {
      produit: 88, type_mouvement: 'entree', quantite: 37, bin_destination: 21,
    }))
    // ventilation relue du serveur et affichée
    expect(await screen.findByText(/Camionnette 1/)).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/stock/produits/88/emplacements/')
  })

  it('affiche le 400 transfert sans casier', async () => {
    // ERR-ASTK196 — le corps d'erreur vient du contrat (affirmé côté serveur
    // par test_contrats_wms_astk.py), jamais retapé à la main.
    const corps = MV.exemple_erreur_400_transfert_sans_casier
    api.post.mockRejectedValue({ response: { status: 400, data: corps } })
    monter()
    await scanner('MIC-001')
    await screen.findByText(/Micro-onduleur/)
    fireEvent.change(screen.getByLabelText('Quantité'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: /Valider le mouvement/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(corps.bin_source[0])
  })

  it('refuse 7.5 sous le champ', async () => {
    monter()
    await scanner('MIC-001')
    await screen.findByText(/Micro-onduleur/)
    fireEvent.change(screen.getByLabelText('Quantité'), { target: { value: '7.5' } })
    fireEvent.click(screen.getByRole('button', { name: /Valider le mouvement/i }))
    expect(await screen.findByText(/nombre entier/i)).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Quantité')).toHaveValue(7.5)
  })

  it('un code inconnu affiche le message serveur', async () => {
    monter()
    await scanner('XXX')
    expect(await screen.findByRole('alert')).toHaveTextContent(SC.exemple_erreur_404.detail)
  })

  it('mode retour fournisseur : pré-remplit la ligne depuis le serveur', async () => {
    monter()
    fireEvent.click(screen.getByRole('button', { name: /Retour fournisseur/i }))
    fireEvent.change(screen.getByLabelText('Code scanné'), { target: { value: 'MIC-001' } })
    fireEvent.change(screen.getByLabelText('Quantité'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: /Préparer le retour/i }))
    expect(await screen.findByText(/Import Solar SARL/)).toBeInTheDocument()
    expect(screen.getByText(/RET-FOUR/)).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/stock/scanner/retour-fournisseur/', { params: { code: 'MIC-001', quantite: 1 } })
  })
})
