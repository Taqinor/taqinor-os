import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// ASAV36 — sélecteur de fournisseur à la création d'une réclamation RMA.
// Faux serveur qui applique `_resolve_fournisseur` : le nom est posé si l'id
// est reçu ; sans choix la création reste possible.

const serveur = vi.hoisted(() => ({ claims: [], corps: [] }))
const FOURNISSEURS = [{ id: 5, nom: 'Huawei Maroc' }, { id: 6, nom: 'VEICHI' }]

vi.mock('../../api/savApi', () => ({
  default: {
    getWarrantyClaims: vi.fn(() => Promise.resolve({ data: serveur.claims })),
    getEquipements: vi.fn(() => Promise.resolve({
      data: [{ id: 1, produit_nom: 'Onduleur', numero_serie: 'SN-1' }] })),
    saveWarrantyClaim: vi.fn((id, payload) => {
      serveur.corps.push(payload)
      const nom = FOURNISSEURS.find((f) => f.id === payload.fournisseur_id_ext)?.nom
      serveur.claims.push({
        id: serveur.claims.length + 1, equipement_produit: 'Onduleur',
        equipement_serie: 'SN-1', statut: 'ouvert', rma_ref: '',
        fournisseur_nom_cache: nom ?? '', date_signalement: '2026-10-09', date_resolution: null,
      })
      return Promise.resolve({ data: {} })
    }),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getFournisseurs: vi.fn(() => Promise.resolve({
    data: { count: 2, next: null, results: FOURNISSEURS } })) },
}))

import WarrantyClaimsPage from './WarrantyClaimsPage'

afterEach(() => { cleanup(); serveur.claims.length = 0; serveur.corps.length = 0 })

function rendre() {
  return render(<MemoryRouter><ThemeProvider><WarrantyClaimsPage /></ThemeProvider></MemoryRouter>)
}

async function choisirEquipement(user) {
  await user.click(screen.getAllByRole('combobox').find((c) => /Équipement/.test(c.textContent)))
  await user.click(await screen.findByRole('option', { name: 'Onduleur — SN-1' }))
}

describe('WarrantyClaimsPage — ASAV36 fournisseur', () => {
  it('créer avec un fournisseur : POST fournisseur_id_ext, le nom est affiché', async () => {
    const user = userEvent.setup()
    rendre()
    await choisirEquipement(user)
    await user.click(screen.getByRole('combobox', { name: 'Fournisseur' }))
    await user.click(await screen.findByRole('option', { name: 'Huawei Maroc' }))
    await user.click(screen.getByRole('button', { name: /Créer/ }))
    await waitFor(() => expect(serveur.corps).toHaveLength(1))
    expect(serveur.corps[0].fournisseur_id_ext).toBe(5)
    await waitFor(() => expect(screen.getAllByText('Huawei Maroc').length).toBeGreaterThan(0))
  }, 60000)

  it('sans choix : création possible, colonne « non renseigné »', async () => {
    const user = userEvent.setup()
    rendre()
    await choisirEquipement(user)
    await user.click(screen.getByRole('button', { name: /Créer/ }))
    await waitFor(() => expect(serveur.corps).toHaveLength(1))
    expect('fournisseur_id_ext' in serveur.corps[0]).toBe(false)
    await waitFor(() => expect(screen.getAllByText('non renseigné').length).toBeGreaterThan(0))
  }, 60000)
})
