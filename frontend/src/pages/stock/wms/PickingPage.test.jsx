import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK217 — écran « Picking » : vagues, prélèvement, comptages tournants,
   productivité / pertes. Réponses = contrat committé `wms_picking.json`
   (ASTK161) ; seul axios est mocké.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import PickingPage from './PickingPage'

const R = documentContrat('stock', 'wms_picking').routes
const VAGUES = R.vagues_picking.exemple
const VAGUE_LANCEE = R.vague_lancer.exemple

let etatVagues
function brancher() {
  etatVagues = VAGUES
  api.get.mockImplementation((url) => {
    if (url === '/stock/vagues-picking/') return Promise.resolve({ data: etatVagues })
    if (url === '/stock/plans-comptage-tournant/') return Promise.resolve({ data: R.plans_comptage_tournant.exemple })
    if (url === '/stock/entrepot/productivite/') return Promise.resolve({ data: R.entrepot_productivite.exemple })
    if (url === '/stock/entrepot/pertes/') return Promise.resolve({ data: R.entrepot_pertes.exemple })
    if (url === '/stock/tache-retour/') return Promise.resolve({ data: R.tache_retour.exemple })
    if (url === '/stock/produits/') return Promise.resolve({ data: { results: [{ id: 88, nom: 'Connecteur MC4' }] } })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><PickingPage /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK217 — PickingPage', () => {
  it('crée puis lance une vague', async () => {
    api.post.mockImplementation((url) => {
      if (url === '/stock/vagues-picking/') return Promise.resolve({ data: R.vagues_picking.exemple_element })
      if (url === '/stock/vagues-picking/14/lancer/') {
        etatVagues = { ...VAGUES, results: [VAGUE_LANCEE] }
        return Promise.resolve({ data: VAGUE_LANCEE })
      }
      return Promise.reject(new Error(`POST inattendu ${url}`))
    })
    monter()
    // création : un besoin (produit 88 × 5) puis « Créer la vague »
    fireEvent.change(await screen.findByLabelText('Produit'), { target: { value: '88' } })
    fireEvent.change(screen.getByLabelText('Quantité à prélever'), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter le besoin/i }))
    fireEvent.click(screen.getByRole('button', { name: /Créer la vague/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/vagues-picking/', {
      besoins: [{ produit_id: 88, quantite: 5 }], note: '',
    }))
    // lancement de la vague brouillon listée
    fireEvent.click(await screen.findByRole('button', { name: /Lancer la vague/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/vagues-picking/14/lancer/'))
    expect(await screen.findByText(/Lancée/)).toBeInTheDocument()
  })

  it('prélever affiche le 400 serveur', async () => {
    etatVagues = { ...VAGUES, results: [VAGUE_LANCEE] }
    api.post.mockRejectedValue({
      response: { status: 400, data: R.vague_prelever_ligne.exemple_erreur_400 },
    })
    monter()
    fireEvent.change(await screen.findByLabelText('Quantité prélevée ligne 61'), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: /Prélever/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(R.vague_prelever_ligne.exemple_erreur_400.detail)
    expect(api.post).toHaveBeenCalledWith('/stock/vagues-picking/14/lignes/61/prelever/', { quantite: 9 })
  })

  it('prélever relit les quantités du serveur', async () => {
    etatVagues = { ...VAGUES, results: [VAGUE_LANCEE] }
    api.post.mockImplementation(() => {
      etatVagues = { ...VAGUES, results: [R.vague_prelever_ligne.exemple] }
      return Promise.resolve({ data: R.vague_prelever_ligne.exemple })
    })
    monter()
    fireEvent.change(await screen.findByLabelText('Quantité prélevée ligne 61'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: /Prélever/i }))
    expect(await screen.findByText(/reste 3/i)).toBeInTheDocument()
  })

  it('configure la libération de la vague en brouillon', async () => {
    api.post.mockResolvedValue({ data: R.vague_configurer_liberation.exemple })
    monter()
    fireEvent.change(await screen.findByLabelText('Mode de libération vague 14'), { target: { value: 'auto_seuil' } })
    fireEvent.change(screen.getByLabelText('Seuil de lignes vague 14'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer la libération/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/stock/vagues-picking/14/configurer-liberation/', { mode: 'auto_seuil', seuil_lignes: 10 }))
  })

  it('générer les comptages tournants', async () => {
    api.post.mockResolvedValue({ data: R.plans_comptage_generer.exemple })
    monter()
    fireEvent.click(await screen.findByRole('tab', { name: /Comptages/i }))
    expect(await screen.findByText(/30 jours/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Générer les comptages/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/plans-comptage-tournant/generer/'))
    expect(await screen.findByText(/INV-2026-10-0003/)).toBeInTheDocument()
  })

  it('affiche productivité et pertes', async () => {
    monter()
    fireEvent.click(await screen.findByRole('tab', { name: /Productivité/i }))
    expect(await screen.findByText('magasinier1')).toBeInTheDocument()
    expect(await screen.findByText('Casse')).toBeInTheDocument()
  })
})
