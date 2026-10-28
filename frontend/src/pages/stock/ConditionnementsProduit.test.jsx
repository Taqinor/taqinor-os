import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { makeAuthStore as makeStore, renderStockPage } from './stockPage.testHelpers.jsx'

/* ============================================================================
   WIR109 — XSTK15 : conditionnements d'achat d'un produit (« Touret 100 m »,
   « Carton 50 »). CRUD complet, jusqu'ici backend-only.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getConditionnementsProduit: vi.fn(),
    createConditionnementProduit: vi.fn(),
    updateConditionnementProduit: vi.fn(),
    deleteConditionnementProduit: vi.fn(),
    getProduits: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import ConditionnementsProduit from './ConditionnementsProduit'

const renderPage = (store = makeStore()) => renderStockPage(ConditionnementsProduit, store)

describe('ConditionnementsProduit (WIR109)', () => {
  it('liste les conditionnements existants', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [{ id: 1, nom: 'Câble 6mm²' }] })
    stockApi.getConditionnementsProduit.mockResolvedValue({
      data: [{ id: 1, nom: 'Touret 100 m', produit_nom: 'Câble 6mm²', facteur: 100, unite_stock: 'm' }],
    })

    renderPage()
    // La grille existe dès le premier rendu (0 ligne pendant le chargement) :
    // la ligne s'attend (findBy), sinon course perdue sous couverture
    // (nocturne frontend-full 40664182387, aria-rowcount="0").
    const grid = await screen.findByRole('grid', { name: 'Conditionnements produit' })
    expect(await within(grid).findByText('Touret 100 m')).toBeInTheDocument()
  })

  it('crée un conditionnement rattaché à un produit', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [{ id: 1, nom: 'Câble 6mm²' }] })
    stockApi.getConditionnementsProduit.mockResolvedValue({ data: [] })
    stockApi.createConditionnementProduit.mockResolvedValue({ data: {} })

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Nouveau conditionnement/ }))

    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('combobox'))
    await userEvent.click(await screen.findByRole('option', { name: 'Câble 6mm²' }))
    // Le champ est `required` : le libellé accessible inclut l'astérisque
    // (aria-hidden n'exclut PAS le texte de son nœud, cf. Label.jsx) — on
    // matche donc « Nom » en préfixe plutôt qu'en chaîne exacte.
    await userEvent.type(within(dialog).getByLabelText(/^Nom/), 'Touret 100 m')
    await userEvent.type(within(dialog).getByLabelText(/Facteur/), '100')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(stockApi.createConditionnementProduit).toHaveBeenCalledWith({
        produit: 1, nom: 'Touret 100 m', facteur: 100, code_barres: null,
      })
    })
  })

  it('supprime un conditionnement', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [] })
    stockApi.getConditionnementsProduit.mockResolvedValue({
      data: [{ id: 1, nom: 'Touret 100 m', produit_nom: 'Câble 6mm²', facteur: 100, unite_stock: 'm' }],
    })
    stockApi.deleteConditionnementProduit.mockResolvedValue({})
    const natif = vi.spyOn(window, 'confirm')

    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Conditionnements produit' })
    await userEvent.click(within(grid).getByRole('button', { name: 'Supprimer' }))
    // ASTK231 — confirmation par l'AlertDialog commune, sans dialogue natif.
    const dialog = await screen.findByRole('alertdialog')
    expect(stockApi.deleteConditionnementProduit).not.toHaveBeenCalled()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    expect(natif).not.toHaveBeenCalled()
    natif.mockRestore()

    await waitFor(() => {
      expect(stockApi.deleteConditionnementProduit).toHaveBeenCalledWith(1)
    })
  })
})
