import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WR3 — « Pilotage stock » : les quatre rapports analytics prêts côté backend
   (réappro / prévisions / rotation / péremptions) rendent, et l'auto-PO génère
   un BCF brouillon en un clic (generer-bcf-reappro/).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    produitsAReapprovisionner: vi.fn(),
    previsionsReappro: vi.fn(),
    rotationStock: vi.fn(),
    expirantBientot: vi.fn(),
    genererBcfReappro: vi.fn(),
    analyseAchatsXlsx: vi.fn(),
    analyseAchatsPdf: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import PilotageStock from './PilotageStock.jsx'

// VX81 — le nom de fichier stampé lit la société active dans le store auth.
function testStore(companyNom = 'TAQINOR') {
  return configureStore({
    reducer: {
      auth: (s = { user: { company_nom: companyNom } }) => s,
    },
  })
}

function wrapper({ children }) {
  return (
    <Provider store={testStore()}>
      <MemoryRouter>
        <ThemeProvider>{children}</ThemeProvider>
      </MemoryRouter>
    </Provider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  stockApi.produitsAReapprovisionner.mockResolvedValue({
    data: [{
      produit_id: 1, nom: 'Panneau 550', sku: 'PAN-550',
      quantite_stock: 2, seuil_alerte: 5, quantite_suggere: 10,
      fournisseur_id: 3, fournisseur_nom: 'JA Solar', prix_achat: '700.00',
    }],
  })
  stockApi.previsionsReappro.mockResolvedValue({
    data: [{
      produit_id: 1, nom: 'Panneau 550', sku: 'PAN-550',
      consommation_mensuelle_moy: 4.5, quantite_stock: 2, quantite_suggeree: 9,
    }],
  })
  stockApi.rotationStock.mockResolvedValue({
    data: [{
      produit_id: 2, nom: 'Onduleur mort', sku: 'OND-1',
      quantite_stock: 3, valeur_stock: '1500.00',
      derniere_sortie: null, jours_sans_mouvement: null, bucket: 'immobile',
    }],
  })
  stockApi.expirantBientot.mockResolvedValue({
    data: [{
      produit_id: 5, produit_nom: 'Batterie', numero_lot: 'LOT-9',
      date_peremption: '2026-08-01', jours_restants: 20, reception_ref: 'REC-3',
    }],
  })
})

describe('WR3 — rendu des quatre rapports', () => {
  it('affiche réappro, prévisions, rotation et péremptions', async () => {
    render(<PilotageStock />, { wrapper })
    // Réappro : le fournisseur le moins cher apparaît (Panneau 550 est dans
    // deux rapports — on ancre sur des libellés uniques par section).
    expect(await screen.findByText('JA Solar')).toBeVisible()
    // Rotation : le stock dormant est marqué « Immobile » (badge unique).
    expect(await screen.findByText('Immobile')).toBeVisible()
    expect(screen.getByText(/Onduleur mort/)).toBeVisible()
    // Péremptions : lot + jours restants.
    expect(await screen.findByText('LOT-9')).toBeVisible()
    expect(screen.getByText('Batterie')).toBeVisible()
    // Chaque endpoint a bien été appelé.
    expect(stockApi.produitsAReapprovisionner).toHaveBeenCalled()
    expect(stockApi.previsionsReappro).toHaveBeenCalled()
    expect(stockApi.rotationStock).toHaveBeenCalled()
    expect(stockApi.expirantBientot).toHaveBeenCalled()
  })

  it('affiche un message honnête quand un rapport admin renvoie 403', async () => {
    stockApi.rotationStock.mockRejectedValue({ response: { status: 403 } })
    render(<PilotageStock />, { wrapper })
    expect(await screen.findByText('JA Solar')).toBeVisible()
    // Le message 403 apparaît (dans le KPI + la section rotation).
    await waitFor(() => {
      expect(screen.getAllByText(/Réservé à l['’]administrateur\./).length).toBeGreaterThan(0)
    })
  })
})

describe('WR3 — auto-PO (BCF brouillon en un clic)', () => {
  it('génère un BCF brouillon et confirme avec la référence renvoyée', async () => {
    stockApi.genererBcfReappro.mockResolvedValue({
      data: { bon_commande_id: 12, reference: 'BCF-2026-07-0012', nb_lignes: 3 },
    })
    const onBcfGenere = vi.fn()
    render(<PilotageStock onBcfGenere={onBcfGenere} />, { wrapper })
    const btn = await screen.findByRole('button', { name: /Générer un BCF/ })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(stockApi.genererBcfReappro).toHaveBeenCalled()
    })
    const status = await screen.findByRole('status')
    expect(status.textContent).toContain('BCF-2026-07-0012')
    expect(onBcfGenere).toHaveBeenCalledWith(
      expect.objectContaining({ reference: 'BCF-2026-07-0012' }),
    )
  })

  it('affiche l\'erreur serveur si la génération échoue', async () => {
    stockApi.genererBcfReappro.mockRejectedValue({
      response: { status: 400, data: { detail: 'Aucun produit à réapprovisionner.' } },
    })
    render(<PilotageStock />, { wrapper })
    const btn = await screen.findByRole('button', { name: /Générer un BCF/ })
    fireEvent.click(btn)
    const alert = await screen.findByRole('alert')
    expect(within(alert).queryByText || alert.textContent).toBeTruthy()
    expect(alert.textContent).toContain('Aucun produit à réapprovisionner.')
  })
})

describe('ZPUR9/XPUR24 — rapport « analyse d\'achats » (Excel + PDF)', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    URL.revokeObjectURL = vi.fn()
    window.open = vi.fn(() => ({}))
  })

  it('exporte l\'analyse d\'achats en Excel', async () => {
    stockApi.analyseAchatsXlsx.mockResolvedValue({ data: new Blob(['x']) })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<PilotageStock />, { wrapper })
    const btn = await screen.findByRole('button', { name: /Analyse d'achats \(Excel\)/ })
    fireEvent.click(btn)
    await waitFor(() => expect(stockApi.analyseAchatsXlsx).toHaveBeenCalled())
    clickSpy.mockRestore()
  })

  // VX81 — le nom de fichier est horodaté (base_societe_AAAAMMJJ.xlsx), jamais
  // un nom nu : deux exports le même jour restent distinguables.
  it('nomme le fichier Excel avec la date + la société (VX81)', async () => {
    stockApi.analyseAchatsXlsx.mockResolvedValue({ data: new Blob(['x']) })
    const anchor = document.createElement('a')
    const createSpy = vi.spyOn(document, 'createElement').mockReturnValue(anchor)
    const clickSpy = vi.spyOn(anchor, 'click').mockImplementation(() => {})
    render(<PilotageStock />, { wrapper })
    const btn = await screen.findByRole('button', { name: /Analyse d'achats \(Excel\)/ })
    fireEvent.click(btn)
    await waitFor(() => expect(clickSpy).toHaveBeenCalled())
    const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    expect(anchor.download).toBe(`analyse-achats_TAQINOR_${stamp}.xlsx`)
    createSpy.mockRestore()
  })

  it('ouvre le rapport PDF « analyse d\'achats » dans un nouvel onglet', async () => {
    stockApi.analyseAchatsPdf.mockResolvedValue({
      data: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
    })
    render(<PilotageStock />, { wrapper })
    const btn = await screen.findByRole('button', { name: /Analyse d'achats \(PDF\)/ })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(stockApi.analyseAchatsPdf).toHaveBeenCalled()
      expect(window.open).toHaveBeenCalledWith('blob:mock-url', '_blank', 'noopener')
    })
  })

  it('un non-autorisé (403) voit un message honnête sur le PDF', async () => {
    stockApi.analyseAchatsPdf.mockRejectedValue({
      response: { status: 403, data: new Blob(['{}'], { type: 'application/json' }) },
    })
    render(<PilotageStock />, { wrapper })
    const btn = await screen.findByRole('button', { name: /Analyse d'achats \(PDF\)/ })
    fireEvent.click(btn)
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/Accès refusé/)
  })
})
