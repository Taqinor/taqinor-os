import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* APAR40 — Paramètres › Données charge la liste COMPLÈTE des produits et des
   kits (pages DRF suivies) : le serveur plafonne `page_size` à 200, donc
   `page_size: 1000` ne rendait que 200 produits sur 311. */

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

const { getProduits, getKits, apiProxy } = vi.hoisted(() => {
  const pagine = (total, prefixe) => vi.fn((params = {}) => {
    const taille = Math.min(params.page_size ?? 50, 200)
    const page = params.page ?? 1
    const debut = (page - 1) * taille
    const fin = Math.min(debut + taille, total)
    const results = []
    for (let i = debut + 1; i <= fin; i += 1) results.push({ id: i, nom: `${prefixe} ${i}` })
    return Promise.resolve({ data: { count: total, results, next: fin < total ? `?page=${page + 1}` : null } })
  })
  const getProduits = pagine(311, 'Produit')
  const getKits = pagine(210, 'Kit')
  const vide = () => Promise.resolve({ data: [] })
  const apiProxy = (overrides = {}) => new Proxy(overrides, {
    get: (t, k) => (k in t ? t[k] : (k === 'then' ? undefined : vi.fn(vide))),
  })
  return { getProduits, getKits, apiProxy }
})
vi.mock('../../api/stockApi', () => ({
  default: apiProxy({ getProduits: (p) => getProduits(p), getKits: (p) => getKits(p) }),
}))

import DonneesSection from './DonneesSection'

describe('APAR40 — listes complètes', () => {
  afterEach(() => { cleanup(); getProduits.mockClear(); getKits.mockClear() })

  it('les 311 produits et les 210 kits sont lus (pages suivies)', async () => {
    render(<MemoryRouter><DonneesSection /></MemoryRouter>)
    await waitFor(() => expect(getProduits).toHaveBeenCalledWith({ page: 2, page_size: 200 }))
    await waitFor(() => expect(getKits).toHaveBeenCalledWith({ page: 2, page_size: 200 }))
    for (const [params] of getProduits.mock.calls) {
      expect(params.page_size).toBeLessThanOrEqual(200)
    }
  })

  it('le sélecteur « Produit remplacé » propose les 311 produits', async () => {
    render(<MemoryRouter><DonneesSection /></MemoryRouter>)
    await waitFor(() => expect(getProduits).toHaveBeenCalledWith({ page: 2, page_size: 200 }))
    const declencheur = (await screen.findAllByRole('combobox'))
      .find((el) => el.textContent.includes('Produit remplacé'))
    await userEvent.setup().click(declencheur)
    const liste = await screen.findByRole('listbox')
    await waitFor(() => expect(within(liste).getAllByRole('option')).toHaveLength(312))
  })
})
