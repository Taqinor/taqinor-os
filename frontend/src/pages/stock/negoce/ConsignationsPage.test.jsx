import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK221 — écran « Consignation ». Réponses = contrat committé
   `negoce_consignation_rfa.json` (ASTK164) ; seul axios est mocké. Les clés
   facture_id / facture_reference viennent de `exemple_nouveau_astk198`.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import ConsignationsPage from './ConsignationsPage'

const R = documentContrat('stock', 'negoce_consignation_rfa').routes
const LISTE = R.consignations.exemple
const DECL_FACTUREE = R.consignation_declarer_consommation.exemple_nouveau_astk198
const PARAMS = R.parametres_negoce.exemple

let etat
function brancher() {
  etat = LISTE
  api.get.mockImplementation((url) => {
    if (url === '/stock/consignations/') return Promise.resolve({ data: etat })
    if (url === '/stock/parametres-negoce/') return Promise.resolve({ data: PARAMS })
    if (url === '/crm/clients/') return Promise.resolve({ data: { results: [{ id: 12, nom: 'Client Alpha' }] } })
    if (url === '/stock/produits/') return Promise.resolve({ data: { results: [{ id: 88, nom: 'Onduleur 3 kW' }] } })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><ConsignationsPage /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK221 — ConsignationsPage', () => {
  it('déclarer affiche la facture créée', async () => {
    api.post.mockImplementation(() => {
      etat = { ...LISTE, results: [{
        ...LISTE.results[0], quantite_consommee_declaree: 8, quantite_restante: 12,
        declarations: [...LISTE.results[0].declarations, DECL_FACTUREE],
      }] }
      return Promise.resolve({ data: DECL_FACTUREE })
    })
    monter()
    fireEvent.change(await screen.findByLabelText('Quantité consommée dépôt 6'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: /Déclarer la consommation/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/stock/consignations/6/declarer-consommation/', expect.objectContaining({ quantite: 2 })))
    const lien = await screen.findByRole('link', { name: /FAC-2026-10-0042/ })
    expect(lien).toHaveAttribute('href', '/ventes/factures?id=311')
    expect(screen.getByText(/Facturée/)).toBeInTheDocument()
  })

  it('affiche le restant du dépôt relu du serveur', async () => {
    monter()
    expect(await screen.findByText(/restant 16/i)).toBeInTheDocument()
  })

  it('refuse une quantité décimale sous le champ', async () => {
    monter()
    fireEvent.change(await screen.findByLabelText('Quantité consommée dépôt 6'), { target: { value: '1.5' } })
    fireEvent.click(screen.getByRole('button', { name: /Déclarer la consommation/i }))
    expect(await screen.findByText(/nombre entier/i)).toBeInTheDocument()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('une consommation supérieure au restant affiche le 400 serveur', async () => {
    api.post.mockRejectedValue({
      response: { status: 400, data: R.consignation_declarer_consommation.exemple_erreur_400 },
    })
    monter()
    fireEvent.change(await screen.findByLabelText('Quantité consommée dépôt 6'), { target: { value: '99' } })
    fireEvent.click(screen.getByRole('button', { name: /Déclarer la consommation/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      R.consignation_declarer_consommation.exemple_erreur_400.detail)
  })

  it('crée un dépôt avec le corps attendu', async () => {
    api.post.mockResolvedValue({ data: R.consignations.exemple_element })
    monter()
    fireEvent.change(await screen.findByLabelText('Client'), { target: { value: '12' } })
    fireEvent.change(screen.getByLabelText('Produit'), { target: { value: '88' } })
    fireEvent.change(screen.getByLabelText('Quantité déposée'), { target: { value: '4' } })
    fireEvent.click(screen.getByRole('button', { name: /Créer le dépôt/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/consignations/', expect.objectContaining({
      client: 12, produit: 88, quantite_deposee: 4 })))
  })

  it('module consignation éteint : message serveur affiché', async () => {
    api.get.mockImplementation((url) => {
      if (url === '/stock/consignations/') {
        return Promise.reject({ response: { status: 403, data: R.consignations.exemple_erreur_403_module_eteint } })
      }
      return Promise.resolve({ data: { results: [] } })
    })
    monter()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      R.consignations.exemple_erreur_403_module_eteint.detail)
  })

  it('réglages : deux champs seulement', async () => {
    monter()
    fireEvent.click(await screen.findByRole('tab', { name: /Réglages/i }))
    const panneau = await screen.findByRole('tabpanel')
    expect(await within(panneau).findByLabelText('Consignation activée')).toBeChecked()
    expect(within(panneau).getByLabelText('Horizon ATP (jours)')).toHaveValue(30)
    expect(within(panneau).getAllByRole('checkbox').length + within(panneau).getAllByRole('spinbutton').length
      + within(panneau).queryAllByRole('textbox').length).toBe(2)
  })

  it('réglages : enregistre uniquement les deux champs', async () => {
    api.patch.mockResolvedValue({ data: PARAMS })
    monter()
    fireEvent.click(await screen.findByRole('tab', { name: /Réglages/i }))
    fireEvent.change(await screen.findByLabelText('Horizon ATP (jours)'), { target: { value: '45' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/i }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/stock/parametres-negoce/', {
      consignation_activee: true, atp_horizon_jours: 45 }))
  })
})
