import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ZMFG12 — mise au rebut motivée / réactivation depuis la fiche équipement.
   savApi mocké. Le panneau fiabilité (autre lane de tests) est mocké ici en
   composant vide pour isoler le test du rebut. */

vi.mock('../../api/savApi', () => ({
  default: {
    getTickets: vi.fn(() => Promise.resolve({ data: [] })),
    updateEquipement: vi.fn(),
    mettreAuRebutEquipement: vi.fn(),
    reactiverRebutEquipement: vi.fn(),
  },
}))
vi.mock('../../api/installationsApi', () => ({ default: { getInstallations: vi.fn() } }))
vi.mock('../../api/stockApi', () => ({ default: { getProduits: vi.fn() } }))
vi.mock('./EquipementFiabilitePanel', () => ({ default: () => null }))

import savApi from '../../api/savApi'
import { EquipementDetail } from './EquipementsPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const baseEquip = {
  id: 3, numero_serie: 'SN-3', statut: 'en_service', mis_au_rebut: false,
}

function renderDetail(equipement) {
  return render(
    <MemoryRouter>
      <EquipementDetail equipement={equipement} onClose={() => {}} onSaved={() => {}} />
    </MemoryRouter>,
  )
}

describe('EquipementDetail — ZMFG12 mise au rebut', () => {
  it('ouvre la confirmation et exige un motif avant de mettre au rebut', async () => {
    savApi.mettreAuRebutEquipement.mockResolvedValue({
      data: { ...baseEquip, mis_au_rebut: true, motif_rebut: 'Casse définitive' },
    })
    renderDetail(baseEquip)
    fireEvent.click(screen.getByRole('button', { name: /Mettre au rebut/ }))
    const confirmBtn = await screen.findByRole('button', { name: 'Confirmer la mise au rebut' })
    expect(confirmBtn).toBeDisabled()

    fireEvent.change(screen.getByLabelText('Motif'), { target: { value: 'Casse définitive' } })
    expect(confirmBtn).not.toBeDisabled()
    fireEvent.click(confirmBtn)

    await waitFor(() => expect(savApi.mettreAuRebutEquipement).toHaveBeenCalledWith(3, 'Casse définitive'))
    expect(await screen.findByText('Équipement mis au rebut.')).toBeInTheDocument()
  })

  it('affiche la bannière de rebut avec le bouton Réactiver pour un équipement déjà au rebut', async () => {
    savApi.reactiverRebutEquipement.mockResolvedValue({
      data: { ...baseEquip, mis_au_rebut: false },
    })
    renderDetail({ ...baseEquip, mis_au_rebut: true, motif_rebut: 'Test' })
    expect(await screen.findByText('Équipement mis au rebut.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Réactiver' }))
    await waitFor(() => expect(savApi.reactiverRebutEquipement).toHaveBeenCalledWith(3))
  })
})
