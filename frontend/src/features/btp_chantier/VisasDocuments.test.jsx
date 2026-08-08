import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT64 — Visas de documents techniques : cycle soumis → en revue →
   approuvé/refusé ; la resoumission automatique (nouvelle version GED) est
   un mécanisme SERVEUR (receivers.py), rien à tester ici côté écran. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { visasList, visasCreate, visasApprouver, visasRefuser } = vi.hoisted(() => ({
  visasList: vi.fn(),
  visasCreate: vi.fn(() => Promise.resolve({ data: { id: 7 } })),
  visasApprouver: vi.fn(() => Promise.resolve({ data: {} })),
  visasRefuser: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    visas: {
      list: (...args) => visasList(...args),
      create: (...args) => visasCreate(...args),
      soumettreObservations: vi.fn(() => Promise.resolve({ data: {} })),
      approuver: (...args) => visasApprouver(...args),
      refuser: (...args) => visasRefuser(...args),
    },
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import VisasDocuments from './VisasDocuments'

beforeEach(() => {
  vi.clearAllMocks()
  visasList.mockResolvedValue({
    data: [
      {
        id: 1, reference: 'VIS-2026-0001', chantier: 5, type_visa: 'plan_execution',
        statut: 'soumis', date_limite: '2026-02-01', nb_resoumissions: 0, observations: '',
      },
      {
        id: 2, reference: 'VIS-2026-0002', chantier: 5, type_visa: 'note_calcul',
        statut: 'approuve_sans_reserve', date_limite: '2026-02-01', nb_resoumissions: 1,
        observations: 'RAS',
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

describe('VisasDocuments (PACT64)', () => {
  it('affiche la liste des visas avec leur statut', async () => {
    withProviders(<VisasDocuments />)
    await waitFor(() => expect(screen.getAllByText('VIS-2026-0001').length).toBeGreaterThan(0))
    expect(screen.getByText('VIS-2026-0002')).toBeInTheDocument()
  })

  it('soumet un nouveau visa', async () => {
    const user = userEvent.setup()
    withProviders(<VisasDocuments />)
    await waitFor(() => expect(screen.getAllByText('VIS-2026-0001').length).toBeGreaterThan(0))

    const chantierOption = await screen.findByRole('option', { name: /Villa Zenith/ })
    await user.selectOptions(screen.getByLabelText('Chantier du visa'), chantierOption)
    await user.type(screen.getByLabelText('ID du document GED'), '77')
    await user.click(screen.getByRole('button', { name: 'Soumettre le visa' }))

    await waitFor(() => expect(visasCreate).toHaveBeenCalledWith(expect.objectContaining({
      chantier: '5', document_ged_id: 77, type_visa: 'autre',
    })))
  })

  it('approuve un visa soumis avec des observations', async () => {
    const user = userEvent.setup()
    withProviders(<VisasDocuments />)
    await waitFor(() => expect(screen.getAllByText('VIS-2026-0001').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await user.type(screen.getByLabelText('Observations de revue'), 'À corriger légèrement')
    await user.click(screen.getByRole('checkbox', { name: 'Approuver avec observations' }))
    await user.click(screen.getByRole('button', { name: 'Approuver' }))

    await waitFor(() => expect(visasApprouver).toHaveBeenCalledWith(1, {
      avecObservations: true, observations: 'À corriger légèrement',
    }))
  })

  it('n’offre plus aucune action sur un visa déjà décidé', async () => {
    const user = userEvent.setup()
    withProviders(<VisasDocuments />)
    await waitFor(() => expect(screen.getAllByText('VIS-2026-0002').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[1])
    expect(await screen.findByText('Visa déjà décidé.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approuver' })).not.toBeInTheDocument()
  })
})
