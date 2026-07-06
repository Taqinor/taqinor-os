import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* FG83 — écran de réclamations garantie fournisseur (RMA). savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    getWarrantyClaims: vi.fn(),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    saveWarrantyClaim: vi.fn(),
  },
}))

import savApi from '../../api/savApi'
import WarrantyClaimsPage, { WarrantyClaimStatutPill } from './WarrantyClaimsPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

// DataTable lit la densité via useDensity → <ThemeProvider> et persiste ses
// filtres via useSearchParams → <Router> (même patron que FleetPage.test.jsx)
// — nécessaire dès qu'une ligne rend la DataTable.
function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('WarrantyClaimsPage — FG83 flux RMA', () => {
  it('affiche la liste des réclamations avec statut et fournisseur', async () => {
    savApi.getWarrantyClaims.mockResolvedValue({
      data: [{
        id: 1, equipement_produit: 'Onduleur Huawei', equipement_serie: 'SN-001',
        fournisseur_nom_cache: 'Huawei Maroc', statut: 'ouvert', rma_ref: '',
        date_signalement: '2026-07-01', date_resolution: null,
      }],
    })
    renderPage(<WarrantyClaimsPage />)
    // DataTable rend simultanément une vue tableau (desktop) et une vue carte
    // (mobile) — chaque cellule apparaît donc deux fois (même patron que
    // FleetPage.test.jsx : getAllByText(...).length).
    await waitFor(() => expect(
      screen.getAllByText(/Onduleur Huawei/).length).toBeGreaterThan(0))
    expect(screen.getAllByText('Huawei Maroc').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Ouvert').length).toBeGreaterThan(0)
  })

  it('affiche un état vide quand aucune réclamation', async () => {
    savApi.getWarrantyClaims.mockResolvedValue({ data: [] })
    render(<WarrantyClaimsPage />)
    expect(await screen.findByText('Aucune réclamation')).toBeInTheDocument()
  })

  it('édite le statut d\'une réclamation et enregistre', async () => {
    savApi.getWarrantyClaims.mockResolvedValue({
      data: [{
        id: 7, equipement_produit: 'Variateur VEICHI', equipement_serie: 'SN-007',
        fournisseur_nom_cache: 'VEICHI', statut: 'ouvert', rma_ref: '',
        date_signalement: '2026-06-01', date_resolution: null,
      }],
    })
    savApi.saveWarrantyClaim.mockResolvedValue({ data: {} })
    renderPage(<WarrantyClaimsPage />)
    // DataTable rend simultanément une vue tableau (desktop) et une vue carte
    // (mobile) — chaque ligne/bouton apparaît donc deux fois ; on agit sur la
    // première occurrence (vue tableau).
    await waitFor(() => expect(
      screen.getAllByText(/Variateur VEICHI/).length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: /Éditer/ })[0])
    fireEvent.click(screen.getAllByRole('button', { name: /Enregistrer/ })[0])
    await waitFor(() => expect(savApi.saveWarrantyClaim).toHaveBeenCalledWith(
      7, expect.objectContaining({ statut: 'ouvert', rma_ref: '' })))
  })
})

describe('WarrantyClaimStatutPill', () => {
  it('rend le libellé FR du statut', () => {
    render(<WarrantyClaimStatutPill claim={{ statut: 'resolu' }} />)
    expect(screen.getByText('Résolu')).toBeInTheDocument()
  })
})
