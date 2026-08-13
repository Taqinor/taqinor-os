import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT62 — Réserves de chantier : carte à pastilles cliquables colorées par
   gravité (pas une liste plate), posée sur un plan (document GED). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { reservesList, reservesCreate, reservesLever } = vi.hoisted(() => ({
  reservesList: vi.fn(),
  reservesCreate: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
  reservesLever: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    reserves: {
      list: (...args) => reservesList(...args),
      create: (...args) => reservesCreate(...args),
      lever: (...args) => reservesLever(...args),
      contester: vi.fn(() => Promise.resolve({ data: {} })),
      photos: vi.fn(() => Promise.resolve({ data: [] })),
    },
  },
}))

vi.mock('../../api/gedApi', () => ({
  default: {
    getVersions: () => Promise.resolve({
      data: [{ id: 501, version: 1 }, { id: 502, version: 2 }],
    }),
    apercuVersionUrl: (id) => `/api/django/ged/versions/${id}/apercu/`,
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import ReservesChantier from './ReservesChantier'

beforeEach(() => {
  vi.clearAllMocks()
  reservesList.mockResolvedValue({
    data: [
      {
        id: 1, chantier: 5, lot: 'Électricité', description: 'Prise manquante',
        gravite: 'majeure', statut: 'ouverte',
        localisation_plan: { document_ged_id: 42, x: 0.25, y: 0.6 },
      },
      {
        id: 2, chantier: 5, lot: 'Plomberie', description: 'Fuite mineure',
        gravite: 'mineure', statut: 'levee',
        localisation_plan: {},
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

describe('ReservesChantier (PACT62)', () => {
  it('affiche les réserves dans la liste de repli tant qu’aucun plan n’est chargé', async () => {
    withProviders(<ReservesChantier />)
    await waitFor(() => expect(screen.getAllByText('Fuite mineure').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Prise manquante').length).toBeGreaterThan(0)
  })

  it('charge un plan et affiche une pastille colorée cliquable, positionnée par x/y', async () => {
    const user = userEvent.setup()
    withProviders(<ReservesChantier />)
    await waitFor(() => expect(screen.getAllByText('Prise manquante').length).toBeGreaterThan(0))

    await user.type(screen.getByLabelText('ID du document GED (plan)'), '42')
    await user.click(screen.getAllByRole('button', { name: 'Charger le plan' })[0])

    const pin = (await screen.findAllByRole('button', { name: /Réserve #1 — Majeure/ }))[0]
    expect(pin.style.left).toBe('25%')
    expect(pin.style.top).toBe('60%')

    await user.click(pin)
    expect(await screen.findByRole('heading', { name: /Réserve #1/ })).toBeInTheDocument()
  })

  it('lève une réserve sélectionnée avec le nom du signataire (loi 53-05)', async () => {
    const user = userEvent.setup()
    withProviders(<ReservesChantier />)
    await waitFor(() => expect(screen.getAllByText('Prise manquante').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await user.type(screen.getByLabelText('Nom du signataire (levée)'), 'Karim B.')
    await user.click(screen.getAllByRole('button', { name: 'Lever' })[0])

    await waitFor(() => expect(reservesLever).toHaveBeenCalledWith(1, 'Karim B.'))
  })

  it('pose une nouvelle réserve en cliquant sur le plan chargé', async () => {
    const user = userEvent.setup()
    withProviders(<ReservesChantier />)
    await waitFor(() => expect(screen.getAllByText('Prise manquante').length).toBeGreaterThan(0))

    const sel_chantierOption = screen.getByLabelText('Chantier')
    await user.selectOptions(sel_chantierOption, within(sel_chantierOption).getByRole('option', { name: /Villa Zenith/ }))

    await user.type(screen.getByLabelText('ID du document GED (plan)'), '42')
    await user.click(screen.getAllByRole('button', { name: 'Charger le plan' })[0])
    await screen.findAllByRole('button', { name: /Réserve #1 — Majeure/ })

    await user.click(screen.getAllByRole('button', { name: 'Ajouter une réserve' })[0])

    const plan = screen.getByTestId('plan-chantier')
    plan.getBoundingClientRect = () => ({
      left: 0, top: 0, width: 200, height: 100, right: 200, bottom: 100,
    })
    fireEvent.click(plan, { clientX: 100, clientY: 50 })

    await user.type(screen.getByLabelText('Description de la réserve'), 'Câble apparent')
    await user.click(screen.getAllByRole('button', { name: 'Poser la réserve' })[0])

    await waitFor(() => expect(reservesCreate).toHaveBeenCalledWith(expect.objectContaining({
      chantier: '5',
      description: 'Câble apparent',
      localisation_plan: { document_ged_id: 42, x: 0.5, y: 0.5 },
    })))
  })
})
