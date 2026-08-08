import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT67 — DGD : solde recalculé côté serveur, verrouillage définitif avec
   déverrouillage admin journalisé, comparatif déboursé sec vs facturé
   (NTCON11, admin/responsable only — jamais un coût côté client). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const {
  decomptesList, decomptesCreate, decomptesNotifier, decomptesFinaliser, debourseVsFacture,
} = vi.hoisted(() => ({
  decomptesList: vi.fn(),
  decomptesCreate: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
  decomptesNotifier: vi.fn(() => Promise.resolve({ data: {} })),
  decomptesFinaliser: vi.fn(() => Promise.resolve({ data: {} })),
  debourseVsFacture: vi.fn(() => Promise.resolve({
    data: {
      main_oeuvre: '1000.00', sous_traitance: '2000.00', materiel: '500.00',
      debourse_sec_total: '3500.00', situations_facturees: '4000.00',
      avenants_approuves: '0.00', facture_total: '4000.00', marge: '500.00',
    },
  })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    decomptes: {
      list: (...args) => decomptesList(...args),
      create: (...args) => decomptesCreate(...args),
      notifier: (...args) => decomptesNotifier(...args),
      contester: vi.fn(() => Promise.resolve({ data: {} })),
      finaliser: (...args) => decomptesFinaliser(...args),
      deverrouiller: vi.fn(() => Promise.resolve({ data: {} })),
      exportPdf: vi.fn(() => Promise.resolve({ data: new Blob(['pdf']) })),
    },
    debourseVsFacture: (...args) => debourseVsFacture(...args),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import DecompteGeneral from './DecompteGeneral'

beforeEach(() => {
  vi.clearAllMocks()
  decomptesList.mockResolvedValue({
    data: [
      {
        id: 1, reference: 'DGD-2026-0001', chantier: 5,
        total_avenants_ht: '15000.00', total_situations_facturees_ht: '40000.00',
        solde_du_ht: '55000.00', statut: 'projet',
      },
    ],
  })
})

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('DecompteGeneral (PACT67)', () => {
  it('affiche les DGD existants', async () => {
    withProviders(<DecompteGeneral />)
    await waitFor(() => expect(screen.getAllByText('DGD-2026-0001').length).toBeGreaterThan(0))
  })

  it('affiche le comparatif déboursé sec vs facturé une fois un chantier choisi', async () => {
    const user = userEvent.setup()
    withProviders(<DecompteGeneral />)
    await waitFor(() => expect(screen.getAllByText('DGD-2026-0001').length).toBeGreaterThan(0))

    const chantierOption = await screen.findByRole('option', { name: /Villa Zenith/ })
    await user.selectOptions(screen.getByLabelText('Filtrer par chantier'), chantierOption)

    await waitFor(() => expect(debourseVsFacture).toHaveBeenCalledWith('5'))
    expect(await screen.findByText('3500.00')).toBeInTheDocument()
  })

  it('crée un DGD', async () => {
    const user = userEvent.setup()
    withProviders(<DecompteGeneral />)
    await waitFor(() => expect(screen.getAllByText('DGD-2026-0001').length).toBeGreaterThan(0))

    const chantierOption = await screen.findByRole('option', { name: /Villa Zenith/ })
    await user.selectOptions(screen.getByLabelText('Chantier du DGD'), chantierOption)
    await user.type(screen.getByLabelText('Montant marché initial HT'), '120000')
    await user.click(screen.getByRole('button', { name: 'Créer le DGD' }))

    await waitFor(() => expect(decomptesCreate).toHaveBeenCalledWith(expect.objectContaining({
      chantier: '5', montant_marche_initial_ht: '120000',
    })))
  })

  it('notifie puis finalise un DGD (verrouillage)', async () => {
    const user = userEvent.setup()
    withProviders(<DecompteGeneral />)
    await waitFor(() => expect(screen.getAllByText('DGD-2026-0001').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: 'Détails' }))
    await user.click(screen.getByRole('button', { name: 'Notifier' }))
    await waitFor(() => expect(decomptesNotifier).toHaveBeenCalledWith(1))

    await user.click(screen.getByRole('button', { name: 'Finaliser (verrouiller)' }))
    await waitFor(() => expect(decomptesFinaliser).toHaveBeenCalledWith(1))
  })
})
