import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK229 (C-ASTK-045, CAT-12) — écran « Nomenclatures de stock (kits) ».
   Réponses = formes RÉELLES du contrat `kits_stock.json` (ASTK168), jamais
   retapées ; seule l'API est simulée (frontière réseau).
     - créer un kit avec un taux de perte → le corps POST le porte ;
     - rouvrir puis réenregistrer sans toucher → le PUT renvoie le MÊME taux
       (jamais remis à 0) ;
     - supprimer passe par une AlertDialog ; les 400 serveur sont affichés.
   ========================================================================== */

vi.mock('../../features/stock/api/kitsApi', () => ({
  default: {
    listKits: vi.fn(),
    getKit: vi.fn(),
    creerKit: vi.fn(),
    modifierKit: vi.fn(),
    supprimerKit: vi.fn(),
    dupliquerKit: vi.fn(),
    revisions: vi.fn(),
    disponibilite: vi.fn(),
    remplacerComposant: vi.fn(),
    listProduits: vi.fn(),
  },
}))

import kitsApi from '../../features/stock/api/kitsApi'
import KitsStock from './KitsStock.jsx'

const R = documentContrat('stock', 'kits_stock').routes
const KIT = R.kits.exemple_element

function renderPage() {
  return render(<MemoryRouter><ThemeProvider><KitsStock /></ThemeProvider></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  kitsApi.listKits.mockResolvedValue({ data: exempleContrat('stock', 'kits_stock') })
  kitsApi.getKit.mockResolvedValue({ data: KIT })
  kitsApi.listProduits.mockResolvedValue({
    data: [{ id: 88, nom: 'Panneau 550 W', sku: 'PV550' }, { id: 89, nom: 'Panneau 600 W', sku: 'PV600' }],
  })
  kitsApi.creerKit.mockResolvedValue({ data: KIT })
  kitsApi.modifierKit.mockResolvedValue({ data: KIT })
  kitsApi.supprimerKit.mockResolvedValue({ data: null })
})

describe('ASTK229 — nomenclatures de stock (kits)', () => {
  it('créer un kit avec taux de perte', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Nouveau kit/ }))
    fireEvent.change(screen.getByLabelText('Nom du kit'), { target: { value: 'Kit 3 kWc' } })
    await waitFor(() => expect(kitsApi.listProduits).toHaveBeenCalled())
    await screen.findAllByRole('option', { name: /Panneau 550 W/ })
    fireEvent.change(screen.getByLabelText('Produit du composant 1'), { target: { value: '88' } })
    fireEvent.change(screen.getByLabelText('Quantité du composant 1'), { target: { value: '6' } })
    fireEvent.change(screen.getByLabelText('Taux de perte du composant 1'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le kit' }))
    await waitFor(() => expect(kitsApi.creerKit).toHaveBeenCalled())
    expect(kitsApi.creerKit.mock.calls[0][0]).toEqual({
      nom: 'Kit 3 kWc', sku: null, description: '',
      composants: [{ produit: 88, quantite: '6', taux_perte_pct: '5' }],
    })
    expect(await screen.findByText('Kit enregistré.')).toBeInTheDocument()
  })

  it('réenregistrer sans toucher conserve taux_perte_pct', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Éditer/ }))
    await waitFor(() => expect(kitsApi.getKit).toHaveBeenCalledWith(KIT.id))
    expect(await screen.findByLabelText('Taux de perte du composant 1')).toHaveValue(Number(KIT.composants[0].taux_perte_pct))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le kit' }))
    await waitFor(() => expect(kitsApi.modifierKit).toHaveBeenCalled())
    const [id, corps] = kitsApi.modifierKit.mock.calls[0]
    expect(id).toBe(KIT.id)
    expect(corps.composants).toEqual(KIT.composants.map((c) => ({
      produit: c.produit, quantite: c.quantite, taux_perte_pct: c.taux_perte_pct,
    })))
  })

  it('la suppression demande une confirmation (AlertDialog)', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Supprimer/ }))
    expect(kitsApi.supprimerKit).not.toHaveBeenCalled()
    expect(await screen.findByText('Supprimer le kit ?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(kitsApi.supprimerKit).toHaveBeenCalledWith(KIT.id))
  })

  it('affiche le refus serveur (400) mot pour mot', async () => {
    kitsApi.creerKit.mockRejectedValue({ response: { status: 400, data: R.kits.exemple_erreur_400_quantite } })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Nouveau kit/ }))
    fireEvent.change(screen.getByLabelText('Nom du kit'), { target: { value: 'Kit invalide' } })
    await screen.findAllByRole('option', { name: /Panneau 550 W/ })
    fireEvent.change(screen.getByLabelText('Produit du composant 1'), { target: { value: '88' } })
    fireEvent.change(screen.getByLabelText('Quantité du composant 1'), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer le kit' }))
    expect(await screen.findByText('La quantité doit être positive.')).toBeInTheDocument()
  })
})
