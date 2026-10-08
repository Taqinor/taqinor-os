import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK220 — écran « Expéditions ». Réponses = contrat committé
   `wms_expedition.json` (ASTK163), jamais retapées ; seul axios est mocké.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import ExpeditionsPage from './ExpeditionsPage'

const R = documentContrat('stock', 'wms_expedition').routes
const UNITE_SCELLEE = R.unites_logistiques_sceller.exemple

function brancher({ unites = R.unites_logistiques.exemple } = {}) {
  api.get.mockImplementation((url) => {
    if (url === '/stock/unites-logistiques/') return Promise.resolve({ data: unites })
    if (url === '/stock/plans-chargement/') return Promise.resolve({ data: R.plans_chargement.exemple })
    if (url === '/stock/expeditions/') return Promise.resolve({ data: R.expeditions.exemple })
    if (url === '/stock/retours-client/') return Promise.resolve({ data: R.retours_client.exemple })
    if (url === '/stock/mouvements-rebut/') return Promise.resolve({ data: R.mouvements_rebut.exemple })
    if (url.includes('verifier-capacite')) return Promise.resolve({ data: R.plans_chargement_verifier_capacite.exemple })
    if (url === '/stock/produits/') return Promise.resolve({ data: { results: [{ id: 5, nom: 'Panneau 550 W' }] } })
    if (url === '/crm/clients/') return Promise.resolve({ data: { results: [{ id: 7, nom: 'Client Test' }] } })
    if (url.includes('bin-locations')) return Promise.resolve({ data: { results: [{ id: 3, code: 'A-01-02' }] } })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><ExpeditionsPage /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK220 — ExpeditionsPage', () => {
  it('une unité en préparation est éditable et scellable', async () => {
    api.post.mockResolvedValue({ data: UNITE_SCELLEE })
    monter()
    const champ = await screen.findByLabelText(/Dimensions de l'unité 000000000000000012/)
    expect(champ).not.toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /Sceller l'unité/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/unites-logistiques/12/sceller/'))
  })

  it('sceller désactive l\'édition', async () => {
    brancher({ unites: { ...R.unites_logistiques.exemple, results: [UNITE_SCELLEE] } })
    monter()
    const champ = await screen.findByLabelText(/Dimensions de l'unité 000000000000000012/)
    expect(champ).toBeDisabled()
    expect(screen.queryByRole('button', { name: /Sceller l'unité/i })).not.toBeInTheDocument()
  })

  it('un PATCH refusé affiche le message serveur', async () => {
    api.patch.mockRejectedValue({
      response: { status: 400, data: R.unites_logistiques.exemple_erreur_400_scellee },
    })
    monter()
    const champ = await screen.findByLabelText(/Dimensions de l'unité 000000000000000012/)
    fireEvent.change(champ, { target: { value: '10x10x10' } })
    fireEvent.blur(champ)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      R.unites_logistiques.exemple_erreur_400_scellee.detail[0])
  })

  it('générer l\'étiquette appelle generer-etiquette', async () => {
    api.post.mockResolvedValue({ data: R.expeditions_generer_etiquette.exemple })
    monter()
    const section = await screen.findByRole('region', { name: /Expéditions transporteur/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Générer l'étiquette/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/expeditions/8/generer-etiquette/'))
    expect(await screen.findByText('Étiquette générée.')).toBeInTheDocument()
  })

  it('receptionner un retour client', async () => {
    api.post.mockResolvedValue({ data: R.retours_client_receptionner.exemple })
    monter()
    const section = await screen.findByRole('region', { name: /Retours client/i })
    expect(await within(section).findByText('RET-2026-0002')).toBeInTheDocument()
    fireEvent.click(within(section).getByRole('button', { name: /Réceptionner le retour/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/retours-client/2/receptionner/'))
  })

  it('une erreur de réception est affichée telle quelle', async () => {
    api.post.mockRejectedValue({
      response: { status: 400, data: R.retours_client_receptionner.exemple_erreur_400 },
    })
    monter()
    const section = await screen.findByRole('region', { name: /Retours client/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Réceptionner le retour/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      R.retours_client_receptionner.exemple_erreur_400.detail)
  })

  it('déclare un rebut avec le motif choisi', async () => {
    api.post.mockResolvedValue({ data: R.mouvements_rebut.exemple_element })
    monter()
    const section = await screen.findByRole('region', { name: /Rebuts/i })
    expect(await within(section).findByText(/Panneau 550 W × 2/)).toBeInTheDocument()
    fireEvent.change(await within(section).findByLabelText('Produit du rebut'), { target: { value: '5' } })
    fireEvent.change(within(section).getByLabelText('Quantité du rebut'), { target: { value: '2' } })
    fireEvent.click(within(section).getByRole('button', { name: /Déclarer le rebut/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/stock/mouvements-rebut/', { produit: 5, quantite: 2, motif: 'casse' }))
  })

  it('vérifie la capacité d\'un plan de chargement', async () => {
    monter()
    const section = await screen.findByRole('region', { name: /Plans de chargement/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Vérifier la capacité/i }))
    expect(await within(section).findByText(/dans la capacité/i)).toBeInTheDocument()
  })
})
