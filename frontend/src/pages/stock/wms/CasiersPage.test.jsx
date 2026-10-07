import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK215 — écran « Casiers » : les réponses viennent du CONTRAT COMMITTÉ
   (`wms_casiers.json`, ASTK160), jamais retapées. Seul le module axios est
   mocké (aucun mock d'une source interne).
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import CasiersPage from './CasiersPage'

const ROUTES = documentContrat('stock', 'wms_casiers').routes
const SEUILS = ROUTES.seuils_reappro_casier.exemple
const TACHES = ROUTES.taches_reappro_interne.exemple
const SOUS_SEUIL = ROUTES.casiers_a_reapprovisionner.exemple
const HISTORIQUE = ROUTES.casier_historique.exemple
const RESLOTTING = ROUTES.reslotting_suggestions.exemple
const EXECUTE = ROUTES.taches_reappro_interne_executer.exemple

function brancherLectures({ taches = TACHES } = {}) {
  api.get.mockImplementation((url) => {
    if (url.includes('seuils-reappro-casier')) return Promise.resolve({ data: SEUILS })
    if (url.includes('taches-reappro-interne')) return Promise.resolve({ data: taches })
    if (url.includes('casiers-a-reapprovisionner')) return Promise.resolve({ data: SOUS_SEUIL })
    if (url.includes('/historique/')) return Promise.resolve({ data: HISTORIQUE })
    if (url.includes('reslotting-suggestions')) return Promise.resolve({ data: RESLOTTING })
    if (url.includes('bin-locations')) return Promise.resolve({ data: { results: [{ id: 21, code: 'P-01-01' }] } })
    if (url.includes('emplacements')) return Promise.resolve({ data: { results: [{ id: 3, nom: 'Dépôt principal' }] } })
    if (url.includes('produits')) return Promise.resolve({ data: { results: [{ id: 88, nom: 'Connecteur MC4' }] } })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><CasiersPage /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancherLectures() })
afterEach(() => { cleanup() })

describe('ASTK215 — CasiersPage', () => {
  it('liste les casiers sous seuil', async () => {
    monter()
    const section = await screen.findByRole('region', { name: /Casiers à réapprovisionner/i })
    expect(await within(section).findByText('P-01-01')).toBeInTheDocument()
    expect(within(section).getByText('Connecteur MC4')).toBeInTheDocument()
    expect(within(section).getByText('37')).toBeInTheDocument()
  })

  it('Exécuter une tâche appelle executer puis recharge', async () => {
    api.post.mockResolvedValue({ data: EXECUTE })
    monter()
    const section = await screen.findByRole('region', { name: /Tâches de réappro/i })
    const bouton = await within(section).findByRole('button', { name: /Exécuter/i })
    const lecturesAvant = api.get.mock.calls.filter(([u]) => u.includes('taches-reappro-interne')).length
    fireEvent.click(bouton)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/taches-reappro-interne/9/executer/'))
    await waitFor(() => {
      const apres = api.get.mock.calls.filter(([u]) => u.includes('taches-reappro-interne')).length
      expect(apres).toBeGreaterThan(lecturesAvant)
    })
  })

  it('un 409 serveur est affiché tel quel', async () => {
    api.post.mockRejectedValue({
      response: { status: 409, data: { detail: 'Quantité source insuffisante dans S-01-01.' } },
    })
    monter()
    const section = await screen.findByRole('region', { name: /Tâches de réappro/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Exécuter/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Quantité source insuffisante dans S-01-01.')
  })

  it('génère les tâches avec POST casiers-a-reapprovisionner', async () => {
    api.post.mockResolvedValue({ data: ROUTES.casiers_a_reapprovisionner.exemple_post })
    monter()
    fireEvent.click(await screen.findByRole('button', { name: /Générer les tâches/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/casiers-a-reapprovisionner/'))
    expect(await screen.findByText(/1 tâche/i)).toBeInTheDocument()
  })

  it('crée un seuil avec le corps du contrat', async () => {
    api.post.mockResolvedValue({ data: ROUTES.seuils_reappro_casier.exemple_element })
    monter()
    await screen.findByRole('region', { name: /Seuils de réappro/i })
    fireEvent.change(await screen.findByLabelText('Casier'), { target: { value: '21' } })
    fireEvent.change(screen.getByLabelText('Produit'), { target: { value: '88' } })
    fireEvent.change(screen.getByLabelText('Seuil'), { target: { value: '10' } })
    fireEvent.change(screen.getByLabelText('Quantité cible'), { target: { value: '40' } })
    fireEvent.click(screen.getByRole('button', { name: /Ajouter le seuil/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/stock/seuils-reappro-casier/', { bin: 21, produit: 88, seuil: 10, quantite_cible: 40, actif: true }))
  })

  it("supprime un seuil après confirmation en ligne (aucune boîte native)", async () => {
    api.delete.mockResolvedValue({ data: null })
    const natif = vi.spyOn(window, 'confirm')
    monter()
    const section = await screen.findByRole('region', { name: /Seuils de réappro/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Supprimer/i }))
    expect(api.delete).not.toHaveBeenCalled()
    fireEvent.click(within(section).getByRole('button', { name: /Confirmer/i }))
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/stock/seuils-reappro-casier/4/'))
    expect(natif).not.toHaveBeenCalled()
  })

  it("ouvre l'historique d'un casier avec l'auteur", async () => {
    monter()
    const section = await screen.findByRole('region', { name: /Casiers à réapprovisionner/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Historique/i }))
    expect(await screen.findByText('magasinier1')).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/stock/casiers/21/historique/')
  })

  it('lit les suggestions de reslotting', async () => {
    monter()
    expect(await screen.findByText('Onduleur star')).toBeInTheDocument()
    expect(screen.getByText('A-01-02')).toBeInTheDocument()
  })
})
