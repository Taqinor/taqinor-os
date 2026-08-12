import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT68 — Diffusion contrôlée de plans : accusé de réception par
   destinataire + détection d'un plan périmé encore consulté (NTCON13). */

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
  diffusionsList, diffusionsCreate, diffusionsDiffuser, plansPerimes,
} = vi.hoisted(() => ({
  diffusionsList: vi.fn(),
  diffusionsCreate: vi.fn(() => Promise.resolve({ data: { id: 6 } })),
  diffusionsDiffuser: vi.fn(() => Promise.resolve({ data: {} })),
  plansPerimes: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    diffusions: {
      list: (...args) => diffusionsList(...args),
      create: (...args) => diffusionsCreate(...args),
      diffuser: (...args) => diffusionsDiffuser(...args),
      plansPerimes: (...args) => plansPerimes(...args),
    },
  },
}))

vi.mock('../../api/gedApi', () => ({
  default: {
    getUsers: () => Promise.resolve({
      data: [{ id: 11, username: 'meryem', nom: 'Meryem K.' }],
    }),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import DiffusionPlans from './DiffusionPlans'

beforeEach(() => {
  vi.clearAllMocks()
  diffusionsList.mockResolvedValue({
    data: [
      {
        id: 1, chantier: 5, document_ged_id: 42, version_diffusee: 2,
        date_diffusion: null, destinataires_internes: [11], destinataires_externes: [],
        accuse_reception: {},
      },
    ],
  })
  plansPerimes.mockResolvedValue({ data: [] })
})

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('DiffusionPlans (PACT68)', () => {
  it('affiche les diffusions existantes', async () => {
    withProviders(<DiffusionPlans />)
    await waitFor(() => expect(screen.getAllByText('#42').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Pas encore diffusée').length).toBeGreaterThan(0)
  })

  it('signale un plan périmé encore consulté une fois un chantier filtré', async () => {
    plansPerimes.mockResolvedValue({
      data: [{
        document_ged_id: 42, destinataire: 'chef-chantier@taqinor.ma',
        version_consultee: 1, derniere_version: 2, horodatage: '2026-01-05T10:00:00Z',
      }],
    })
    const user = userEvent.setup()
    withProviders(<DiffusionPlans />)
    await waitFor(() => expect(screen.getAllByText('#42').length).toBeGreaterThan(0))

    const sel_chantierOption = screen.getByLabelText('Filtrer par chantier')
    await user.selectOptions(sel_chantierOption, within(sel_chantierOption).getByRole('option', { name: /Villa Zenith/ }))

    await waitFor(() => expect(plansPerimes).toHaveBeenCalledWith('5'))
    expect((await screen.findAllByText('Plans périmés encore consultés')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/chef-chantier@taqinor.ma/).length).toBeGreaterThan(0)
  })

  it('crée une diffusion avec un destinataire interne et un externe', async () => {
    const user = userEvent.setup()
    withProviders(<DiffusionPlans />)
    await waitFor(() => expect(screen.getAllByText('#42').length).toBeGreaterThan(0))

    const sel_chantierOption = screen.getByLabelText('Chantier de la diffusion')
    await user.selectOptions(sel_chantierOption, within(sel_chantierOption).getByRole('option', { name: /Villa Zenith/ }))
    await user.type(screen.getByLabelText('ID du document GED à diffuser'), '99')

    const sel_userOption = screen.getByLabelText('Destinataires internes')
    await user.selectOptions(sel_userOption, within(sel_userOption).getByRole('option', { name: 'Meryem K.' }))
    await user.type(screen.getByLabelText('Destinataires externes'), 'archi@example.com')

    await user.click(screen.getAllByRole('button', { name: 'Créer la diffusion' })[0])

    await waitFor(() => expect(diffusionsCreate).toHaveBeenCalledWith(expect.objectContaining({
      chantier: '5', document_ged_id: 99, version_diffusee: 1,
      destinataires_internes: [11], destinataires_externes: ['archi@example.com'],
    })))
  })

  it('diffuse un plan pas encore diffusé', async () => {
    const user = userEvent.setup()
    withProviders(<DiffusionPlans />)
    await waitFor(() => expect(screen.getAllByText('#42').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await user.click(screen.getAllByRole('button', { name: 'Diffuser' })[0])

    await waitFor(() => expect(diffusionsDiffuser).toHaveBeenCalledWith(1))
  })
})
