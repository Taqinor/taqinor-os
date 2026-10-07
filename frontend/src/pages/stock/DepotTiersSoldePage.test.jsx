import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK223 — page publique « solde du dépositaire » (/depot-tiers/:token).
   Réponses = contrat committé `negoce_consignation_rfa.json` (ASTK164).
   ========================================================================== */

const client = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('axios', () => ({ default: { create: vi.fn(() => client) } }))

import DepotTiersSoldePage from './DepotTiersSoldePage'

const S = documentContrat('stock', 'negoce_consignation_rfa').routes.public_tiers_solde

const monter = () => render(
  <MemoryRouter initialEntries={['/depot-tiers/tk_9f2c']}>
    <Routes><Route path="/depot-tiers/:token" element={<DepotTiersSoldePage />} /></Routes>
  </MemoryRouter>)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('ASTK223 — DepotTiersSoldePage', () => {
  it('page publique : solde sans prix', async () => {
    // Une clé de prix fictive injectée dans la réponse ne doit JAMAIS s'afficher.
    client.get.mockResolvedValue({ data: {
      ...S.exemple,
      lignes: S.exemple.lignes.map((l) => ({ ...l, prix_vente: 4321, prix_achat: 1234 })),
    } })
    monter()
    expect(await screen.findByText('Client Alpha')).toBeInTheDocument()
    expect(screen.getByText('Panneau 550 W')).toBeInTheDocument()
    expect(screen.getByText('PAN-550')).toBeInTheDocument()
    expect(screen.getByText(/Dépôt-vente Alpha/)).toBeInTheDocument()
    expect(client.get).toHaveBeenCalledWith('/api/django/public/stock/tiers/tk_9f2c/solde/')
    expect(document.body.textContent).not.toMatch(/4321|1234|prix/i)
  })

  it('lien révoqué : message serveur', async () => {
    client.get.mockRejectedValue({ response: { status: 404, data: S.exemple_erreur_404 } })
    monter()
    expect(await screen.findByRole('alert')).toHaveTextContent(S.exemple_erreur_404.detail)
  })

  it('solde vide : message honnête', async () => {
    client.get.mockResolvedValue({ data: S.exemple_vide })
    monter()
    expect(await screen.findByText(/Aucun article/i)).toBeInTheDocument()
  })
})
