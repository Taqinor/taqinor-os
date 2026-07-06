import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ZPUR3 — Modèles de bon de commande fournisseur (« purchase templates ») :
   liste, création, et génération d'un BCF brouillon pré-rempli.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getModelesBcf: vi.fn(),
    getModeleBcf: vi.fn(),
    createModeleBcf: vi.fn(),
    updateModeleBcf: vi.fn(),
    deleteModeleBcf: vi.fn(),
    genererModeleBcf: vi.fn(),
    getFournisseurs: vi.fn(),
    getProduits: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import ModelesBcf from './ModelesBcf.jsx'

function wrapper({ children }) {
  return (
    <MemoryRouter>
      <ThemeProvider>{children}</ThemeProvider>
    </MemoryRouter>
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
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  stockApi.getModelesBcf.mockResolvedValue({
    data: [
      { id: 1, nom: 'Réassort panneaux', fournisseur: 3, fournisseur_nom: 'JA Solar', lignes: [{ id: 1, produit: 7, quantite: 10 }] },
    ],
  })
  stockApi.getFournisseurs.mockResolvedValue({ data: [{ id: 3, nom: 'JA Solar' }] })
  stockApi.getProduits.mockResolvedValue({ data: [{ id: 7, nom: 'Panneau 550', sku: 'PAN-550' }] })
})

describe('ZPUR3 — liste des modèles de BCF', () => {
  it('affiche les modèles chargés', async () => {
    render(<ModelesBcf />, { wrapper })
    expect((await screen.findAllByText('Réassort panneaux'))[0]).toBeInTheDocument()
    expect(screen.getAllByText('JA Solar')[0]).toBeInTheDocument()
  })

  it('« Générer un BCF » appelle genererModeleBcf avec le fournisseur', async () => {
    stockApi.genererModeleBcf.mockResolvedValue({ data: { id: 55, reference: 'BCF-2026-0099' } })
    render(<ModelesBcf />, { wrapper })
    await screen.findAllByText('Réassort panneaux')
    fireEvent.click(screen.getAllByRole('button', { name: /Générer un BCF/ })[0])
    fireEvent.click(await screen.findByRole('button', { name: /^Générer le BCF$/ }))
    await waitFor(() => expect(stockApi.genererModeleBcf).toHaveBeenCalledWith(1, 3))
  })

  it('« Nouveau modèle » ouvre la modale de création', async () => {
    render(<ModelesBcf />, { wrapper })
    await screen.findAllByText('Réassort panneaux')
    fireEvent.click(screen.getByRole('button', { name: /Nouveau modèle/ }))
    expect(screen.getByText('Nouveau modèle de BCF')).toBeInTheDocument()
  })

  it('création : refuse un modèle sans lignes', async () => {
    render(<ModelesBcf />, { wrapper })
    await screen.findAllByText('Réassort panneaux')
    fireEvent.click(screen.getByRole('button', { name: /Nouveau modèle/ }))
    fireEvent.change(screen.getByLabelText('Nom du modèle'), { target: { value: 'Test' } })
    fireEvent.click(screen.getByRole('button', { name: /^Enregistrer$/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/au moins une ligne/)
    expect(stockApi.createModeleBcf).not.toHaveBeenCalled()
  })
})
