import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import { renderAvecAuth } from '../../test/renderAvecAuth'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ADRG149 — l'export du Parc installé (« Exporter Excel » de l'en-tête et
   « Exporter » du tableau) suit la case `installation_export` du module. */

beforeAll(polyfillResizeObserver)

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({ data: { results: [
      { id: 1, reference: 'CH-P1', client_nom: 'Client P', statut: 'receptionne' },
    ], next: null } }),
  },
}))
vi.mock('../../api/importApi', () => ({ default: {}, downloadXlsx: vi.fn() }))

import ParcInstallePage from './ParcInstallePage'

afterEach(() => {
  cleanup()
  try { localStorage.clear() } catch { /* indisponible */ }
})

const monter = (auth) => renderAvecAuth(<ParcInstallePage />, { user: { id: 1 }, ...auth }, { theme: true })

describe('ParcInstallePage — droit d\'export (ADRG149)', () => {
  it('sans installation_export : ni Exporter Excel ni Exporter', async () => {
    monter({ role: 'responsable', role_nom: 'Commercial responsable',
      permissions: ['ventes_voir', 'ventes_creer', 'crm_voir', 'crm_modifier'] })
    await waitFor(() => expect(screen.getAllByText('CH-P1').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', { name: /Exporter/ })).not.toBeInTheDocument()
  })

  it('avec installation_export : Exporter Excel et Exporter présents', async () => {
    monter({ role: 'responsable', role_nom: 'Directeur',
      permissions: ['ventes_voir', 'installation_export', 'installation_gerer'] })
    await waitFor(() => expect(screen.getAllByText('CH-P1').length).toBeGreaterThan(0))
    expect(screen.getByRole('button', { name: /Exporter Excel/ })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Exporter/ }).length).toBeGreaterThanOrEqual(2)
  })
})
