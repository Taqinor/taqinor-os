import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

/* XSTK5 — Picking scan-first : (1) scan hors bon de prélèvement refusé,
   (2) scan valide coche/incrémente la ligne, (3) bascule de mode. */

const pickListFixture = {
  id: 7,
  reference: 'PICK-202607-0003',
  lignes: [
    {
      id: 21, produit: 5, produit_nom: 'Onduleur 5kW', bin_code: 'A-01-01',
      quantite_demandee: 2, quantite_prelevee: 1, preleve: false, ordre: 1,
    },
  ],
}

vi.mock('../../../api/stockApi', () => ({
  default: { resolveCode: vi.fn() },
}))
vi.mock('../../../api/installationsApi', () => ({
  default: {
    getPickList: vi.fn(() => Promise.resolve({ data: pickListFixture })),
    updatePickListLigne: vi.fn(() => Promise.resolve({
      data: { ...pickListFixture.lignes[0], quantite_prelevee: 2, preleve: true },
    })),
  },
}))

import stockApi from '../../../api/stockApi'
import installationsApi from '../../../api/installationsApi'
import PickingScanPanel from './PickingScanPanel'

beforeEach(() => { vi.clearAllMocks() })

async function scanManual(user, code) {
  const input = screen.getByLabelText('Code scanné ou saisi manuellement')
  await user.clear(input)
  await user.type(input, code)
  await user.click(screen.getByRole('button', { name: 'Valider' }))
}

describe('PickingScanPanel', () => {
  it('charge le bon de prélèvement et affiche ses lignes', async () => {
    render(<PickingScanPanel pickListId={7} />)
    await waitFor(() => expect(installationsApi.getPickList).toHaveBeenCalledWith(7))
    expect(await screen.findByText('Onduleur 5kW')).toBeInTheDocument()
  })

  it('scan HORS bon de prélèvement est refusé — aucun PATCH envoyé', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 999, label: 'Inconnu' } })
    render(<PickingScanPanel pickListId={7} />)
    await screen.findByText('Onduleur 5kW')

    await scanManual(user, 'EAN-HORS-LISTE')

    await waitFor(() => expect(stockApi.resolveCode).toHaveBeenCalled())
    expect(await screen.findByRole('alert')).toHaveTextContent('refusé')
    expect(installationsApi.updatePickListLigne).not.toHaveBeenCalled()
  })

  it('scan-par-unité incrémente `quantite_prelevee` et coche `preleve` à la cible', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 5, label: 'Onduleur 5kW' } })
    render(<PickingScanPanel pickListId={7} />)
    await screen.findByText('Onduleur 5kW')

    await scanManual(user, '1234567890123')

    await waitFor(() => expect(installationsApi.updatePickListLigne).toHaveBeenCalledWith(
      21, { quantite_prelevee: 2, preleve: true }))
  })

  it('bascule de mode fait apparaître le champ de saisie de quantité prélevée', async () => {
    const user = userEvent.setup()
    render(<PickingScanPanel pickListId={7} />)
    await screen.findByText('Onduleur 5kW')

    expect(screen.queryByLabelText(/Quantité prélevée/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Saisie quantité' }))
    expect(await screen.findByLabelText(/Quantité prélevée/)).toBeInTheDocument()
  })
})
