import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK224 — écran « Qualité & rappels ». Réponses = contrat committé
   `wms_rappels_qualite.json` (ASTK165), jamais retapées ; seul axios est mocké.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import QualitePage from './QualitePage'

const R = documentContrat('stock', 'wms_rappels_qualite').routes
// Le rappel porte ses blocages (clé NOUVELLE ASTK199 du contrat).
const RAPPELS = [R.alertes_rappel.exemple_nouveau_astk199]

function brancher() {
  api.get.mockImplementation((url) => {
    if (url === '/stock/alertes-rappel/') return Promise.resolve({ data: RAPPELS })
    if (url.includes('/impact/')) return Promise.resolve({ data: R.alertes_rappel_impact.exemple })
    if (url === '/stock/blocages-qualite/') return Promise.resolve({ data: R.blocages_qualite.exemple })
    if (url === '/stock/plans-echantillonnage/') return Promise.resolve({ data: R.plans_echantillonnage.exemple })
    if (url === '/stock/casiers-hazmat/') return Promise.resolve({ data: R.casiers_hazmat.exemple })
    if (url === '/stock/produits/') return Promise.resolve({ data: { results: [{ id: 5, nom: 'Batterie 5 kWh' }] } })
    if (url.includes('bin-locations')) return Promise.resolve({ data: { results: [{ id: 9, code: 'A-HZ-01' }] } })
    if (url === '/stock/categories/') return Promise.resolve({ data: { results: [{ id: 4, nom: 'Batteries' }] } })
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
}

const monter = () => render(<MemoryRouter><QualitePage /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks(); brancher() })
afterEach(() => { cleanup() })

describe('ASTK224 — QualitePage', () => {
  it('un rappel affiche ses blocages', async () => {
    monter()
    const section = await screen.findByRole('region', { name: /Alertes de rappel/i })
    expect(await within(section).findByText(/Blocage 21 — 4 unité/)).toBeInTheDocument()
    expect(within(section).getByText('LOT-2026-07')).toBeInTheDocument()
  })

  it('consulte l\'impact d\'un rappel', async () => {
    monter()
    const section = await screen.findByRole('region', { name: /Alertes de rappel/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Impact du rappel 3/i }))
    expect(await within(section).findByText(/12 en stock/)).toBeInTheDocument()
  })

  it('clôturer lève les blocages', async () => {
    api.post.mockResolvedValue({ data: R.alertes_rappel_cloturer.exemple })
    monter()
    const section = await screen.findByRole('region', { name: /Alertes de rappel/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Clôturer le rappel 3/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/alertes-rappel/3/cloturer/'))
    expect(await screen.findByText('Rappel clôturé.')).toBeInTheDocument()
  })

  it('lève un blocage qualité', async () => {
    api.post.mockResolvedValue({ data: R.blocages_qualite_lever.exemple })
    monter()
    const section = await screen.findByRole('region', { name: /Blocages qualité/i })
    fireEvent.click(await within(section).findByRole('button', { name: /Lever le blocage 21/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/blocages-qualite/21/lever/'))
  })

  it('déclarer un casier compatible', async () => {
    api.post.mockResolvedValue({ data: R.casiers_hazmat.exemple_element })
    monter()
    const section = await screen.findByRole('region', { name: /Casiers compatibles/i })
    fireEvent.change(await within(section).findByLabelText('Casier compatible'), { target: { value: '9' } })
    fireEvent.click(within(section).getByRole('button', { name: /Déclarer le casier compatible/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/stock/casiers-hazmat/', R.casiers_hazmat.exemple_corps))
  })

  it('une erreur serveur est affichée mot pour mot', async () => {
    api.post.mockRejectedValue({
      response: { status: 400, data: R.plans_echantillonnage.exemple_erreur_400 },
    })
    monter()
    const section = await screen.findByRole('region', { name: /Plans d'échantillonnage/i })
    fireEvent.change(await within(section).findByLabelText('Catégorie contrôlée'), { target: { value: '4' } })
    fireEvent.change(within(section).getByLabelText(/Taux d'échantillon/), { target: { value: '150' } })
    fireEvent.click(within(section).getByRole('button', { name: /Enregistrer le plan/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      R.plans_echantillonnage.exemple_erreur_400.taux_echantillon_pct[0])
  })
})
