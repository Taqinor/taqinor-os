import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

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

describe('WarrantyClaimsPage — FG83 flux RMA', () => {
  it('affiche la liste des réclamations avec statut et fournisseur', async () => {
    savApi.getWarrantyClaims.mockResolvedValue({
      data: [{
        id: 1, equipement_produit: 'Onduleur Huawei', equipement_serie: 'SN-001',
        fournisseur_nom_cache: 'Huawei Maroc', statut: 'ouvert', rma_ref: '',
        date_signalement: '2026-07-01', date_resolution: null,
      }],
    })
    render(<WarrantyClaimsPage />)
    expect(await screen.findByText(/Onduleur Huawei/)).toBeInTheDocument()
    expect(screen.getByText('Huawei Maroc')).toBeInTheDocument()
    expect(screen.getByText('Ouvert')).toBeInTheDocument()
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
    render(<WarrantyClaimsPage />)
    await screen.findByText(/Variateur VEICHI/)
    fireEvent.click(screen.getByRole('button', { name: /Éditer/ }))
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
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
