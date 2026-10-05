import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import APERCU from '../../../../backend/django_core/apps/ventes/contract_samples/facture_relance_apercu.json'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const ROWS = [{
  id: 118, reference: 'FAC-2026-10-0007', client_id: 42, client_nom: 'ACME SARL',
  montant_du: 15000, niveau: null,
}]

vi.mock('../../api/ventesApi', () => ({
  default: {
    getRelances: vi.fn(() => Promise.resolve({ data: ROWS })),
    getRelanceApercu: vi.fn(),
    relancerFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({
    confirm: () => Promise.resolve(true),
    confirmDelete: () => Promise.resolve(true),
  }),
}))

import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import RelancesPage from './RelancesPage'

beforeEach(() => {
  api.get.mockImplementation((url) => (url === '/users/'
    ? Promise.resolve({ data: [] }) : Promise.resolve({ data: [] })))
  ventesApi.getRelances.mockResolvedValue({ data: ROWS })
  ventesApi.relancerFacture.mockResolvedValue({ data: {} })
  ventesApi.getRelanceApercu.mockResolvedValue({ data: APERCU.exemple })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const ouvrir = async (user) => {
  render(<MemoryRouter><RelancesPage /></MemoryRouter>)
  await user.click(await screen.findByRole('button', { name: 'Relancer' }))
}

describe('Relancer — niveau + aperçu', () => {
  it('présélectionne niveau_suivant et coche l\'e-mail', async () => {
    const user = userEvent.setup()
    await ouvrir(user)
    expect(await screen.findByTestId('relance-apercu-message')).toBeTruthy()
    const email = screen.getByRole('checkbox', { name: /Envoyer l'email au client/ })
    await waitFor(() => expect(email.getAttribute('data-state')).toBe('checked'))
    await user.click(screen.getByRole('button', { name: 'Consigner' }))
    await waitFor(() => expect(ventesApi.relancerFacture).toHaveBeenCalled())
    const [id, body] = ventesApi.relancerFacture.mock.calls[0]
    expect(id).toBe(118)
    expect(body.niveau).toBe(APERCU.exemple.niveau_suivant.ordre)
    expect(body.envoyer_email).toBe(true)
  })

  it('désactive la case e-mail sans adresse client', async () => {
    ventesApi.getRelanceApercu.mockResolvedValue({
      data: { ...APERCU.exemple, email_client: '', peut_envoyer_email: false },
    })
    const user = userEvent.setup()
    await ouvrir(user)
    expect(await screen.findByText('Aucun e-mail client')).toBeTruthy()
    const email = screen.getByRole('checkbox', { name: /Envoyer l'email au client/ })
    expect(email.disabled).toBe(true)
    expect(email.getAttribute('data-state')).toBe('unchecked')
  })
})
