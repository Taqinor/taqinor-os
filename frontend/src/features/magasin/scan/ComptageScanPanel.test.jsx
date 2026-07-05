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

/* XSTK5 — Comptage scan-first : (1) scan hors session refusé, (2) scan +
   saisie alimente `quantite_comptee` via updateComptageLigne, (3) bascule
   de mode (scan-par-unité incrémente sans attendre de saisie). */

const sessionFixture = {
  id: 3,
  reference: 'CYC-202607-0002',
  lignes: [
    {
      id: 31, produit: 5, produit_nom: 'Onduleur 5kW',
      quantite_theorique: 8, quantite_comptee: null, compte: false,
    },
  ],
}

vi.mock('../../../api/stockApi', () => ({
  default: { resolveCode: vi.fn() },
}))
vi.mock('../../../api/installationsApi', () => ({
  default: {
    getSessionComptage: vi.fn(() => Promise.resolve({ data: sessionFixture })),
    updateComptageLigne: vi.fn(() => Promise.resolve({
      data: { ...sessionFixture.lignes[0], quantite_comptee: 7, compte: true },
    })),
  },
}))

import stockApi from '../../../api/stockApi'
import installationsApi from '../../../api/installationsApi'
import ComptageScanPanel from './ComptageScanPanel'

beforeEach(() => { vi.clearAllMocks() })

async function scanManual(user, code) {
  const input = screen.getByLabelText('Code scanné ou saisi manuellement')
  await user.clear(input)
  await user.type(input, code)
  await user.click(screen.getByRole('button', { name: 'Valider' }))
}

describe('ComptageScanPanel', () => {
  it('charge la session et affiche ses lignes', async () => {
    render(<ComptageScanPanel sessionId={3} />)
    await waitFor(() => expect(installationsApi.getSessionComptage).toHaveBeenCalledWith(3))
    expect(await screen.findByText('Onduleur 5kW')).toBeInTheDocument()
  })

  it('scan HORS session (SKU jamais ajouté) est refusé — aucun PATCH envoyé', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 999, label: 'Inconnu' } })
    render(<ComptageScanPanel sessionId={3} />)
    await screen.findByText('Onduleur 5kW')

    await scanManual(user, 'EAN-HORS-SESSION')

    await waitFor(() => expect(stockApi.resolveCode).toHaveBeenCalled())
    expect(await screen.findByRole('alert')).toHaveTextContent('refusé')
    expect(installationsApi.updateComptageLigne).not.toHaveBeenCalled()
  })

  it('mode saisie-quantité : scan sélectionne la ligne, la quantité tapée alimente le compte', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 5, label: 'Onduleur 5kW' } })
    render(<ComptageScanPanel sessionId={3} />)
    await screen.findByText('Onduleur 5kW')

    // Mode par défaut = saisie-quantité pour le comptage : on tape d'abord.
    await user.type(screen.getByLabelText(/Quantité comptée/), '7')
    await scanManual(user, '1234567890123')

    await waitFor(() => expect(installationsApi.updateComptageLigne).toHaveBeenCalledWith(
      31, { quantite_comptee: 7, compte: true }))
  })

  it('bascule vers scan-par-unité incrémente sans attendre de saisie', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 5, label: 'Onduleur 5kW' } })
    render(<ComptageScanPanel sessionId={3} />)
    await screen.findByText('Onduleur 5kW')

    await user.click(screen.getByRole('radio', { name: 'Scan par unité' }))
    expect(screen.queryByLabelText(/Quantité comptée/)).not.toBeInTheDocument()

    await scanManual(user, '1234567890123')

    await waitFor(() => expect(installationsApi.updateComptageLigne).toHaveBeenCalledWith(
      31, { quantite_comptee: 1, compte: true }))
  })
})
