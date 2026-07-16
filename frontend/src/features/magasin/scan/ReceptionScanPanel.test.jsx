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

/* XSTK5 — Réception scan-first : couvre (1) un scan hors-liste refusé sans
   appel `recevoirBcf`, (2) l'incrément correct en mode scan-par-unité,
   (3) le bascule de mode. La caméra n'est pas testée ici (jsdom n'a pas
   `BarcodeDetector` — repli automatique) : on scanne via le champ manuel,
   qui partage le même chemin `onScan` que le clavier-wedge. */

const bcfFixture = {
  id: 1,
  reference: 'BCF-202607-0001',
  lignes: [
    { id: 11, produit: 5, produit_nom: 'Onduleur 5kW', quantite: 10, quantite_recue: 0 },
    { id: 12, produit: 6, produit_nom: 'Panneau 450W', quantite: 20, quantite_recue: 20 },
  ],
}

vi.mock('../../../api/stockApi', () => ({
  default: {
    getBonCommandeFournisseur: vi.fn(() => Promise.resolve({ data: bcfFixture })),
    resolveCode: vi.fn(),
    recevoirBcf: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

// ZSTK13 — `useStockFlags` lit le profil entreprise ; défaut True (scan +
// lots/séries actifs) = comportement inchangé.
vi.mock('../../../api/parametresApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getProfile: vi.fn(() => Promise.resolve({ data: {} })),
    },
  }
})

import stockApi from '../../../api/stockApi'
import ReceptionScanPanel from './ReceptionScanPanel'

beforeEach(() => { vi.clearAllMocks() })

function renderPanel() {
  return render(<ReceptionScanPanel bonCommandeId={1} />)
}

async function scanManual(user, code) {
  const input = screen.getByLabelText('Code scanné ou saisi manuellement')
  await user.clear(input)
  await user.type(input, code)
  await user.click(screen.getByRole('button', { name: 'Valider' }))
}

describe('ReceptionScanPanel', () => {
  it('charge le BCF et affiche ses lignes', async () => {
    renderPanel()
    await waitFor(() => expect(stockApi.getBonCommandeFournisseur).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Onduleur 5kW')).toBeInTheDocument()
  })

  it('scan HORS-LISTE (produit absent du BCF) est refusé — aucun appel recevoirBcf', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 999, label: 'Inconnu' } })
    renderPanel()
    await screen.findByText('Onduleur 5kW')

    await scanManual(user, 'EAN-INCONNU')

    await waitFor(() => expect(stockApi.resolveCode).toHaveBeenCalledWith('EAN-INCONNU'))
    expect(await screen.findByRole('alert')).toHaveTextContent('refusé')
    expect(stockApi.recevoirBcf).not.toHaveBeenCalled()
  })

  it('scan-par-unité : un scan valide incrémente de 1 la ligne correspondante', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 5, label: 'Onduleur 5kW' } })
    renderPanel()
    await screen.findByText('Onduleur 5kW')

    await scanManual(user, '1234567890123')

    await waitFor(() => expect(stockApi.recevoirBcf).toHaveBeenCalledWith(
      1, [{ ligne: 11, quantite: 1 }]))
  })

  it('bascule de mode fait apparaître le champ de saisie de quantité', async () => {
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText('Onduleur 5kW')

    expect(screen.queryByLabelText(/Quantité à recevoir/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Saisie quantité' }))
    expect(await screen.findByLabelText(/Quantité à recevoir/)).toBeInTheDocument()
  })

  it('scan sur une ligne déjà entièrement reçue ne déclenche aucun appel (reste dû = 0)', async () => {
    const user = userEvent.setup()
    stockApi.resolveCode.mockResolvedValueOnce({ data: { id: 6, label: 'Panneau 450W' } })
    renderPanel()
    await screen.findByText('Panneau 450W')

    await scanManual(user, '9998887776665')

    await waitFor(() => expect(stockApi.resolveCode).toHaveBeenCalled())
    expect(stockApi.recevoirBcf).not.toHaveBeenCalled()
  })
})
