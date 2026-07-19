import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR114 — page Astreintes / Indisponibilités / Récurrences (FG302, ZFSM3). */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const inst = vi.hoisted(() => ({
  getAstreintes: vi.fn(() => Promise.resolve({ data: [] })),
  createAstreinte: vi.fn(() => Promise.resolve({ data: {} })),
  deleteAstreinte: vi.fn(() => Promise.resolve({ data: {} })),
  getIndisponibilites: vi.fn(() => Promise.resolve({ data: [] })),
  createIndisponibilite: vi.fn(() => Promise.resolve({ data: {} })),
  deleteIndisponibilite: vi.fn(() => Promise.resolve({ data: {} })),
  getRecurrencesIntervention: vi.fn(() => Promise.resolve({ data: [] })),
  createRecurrenceIntervention: vi.fn(() => Promise.resolve({ data: {} })),
  deleteRecurrenceIntervention: vi.fn(() => Promise.resolve({ data: {} })),
  getInstallations: vi.fn(() => Promise.resolve({ data: [{ id: 7, reference: 'CH-007' }] })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))
vi.mock('../../api/crmApi', () => ({ default: { getAssignableUsers: () => Promise.resolve({ data: [{ id: 10, username: 'ahmed' }] }) } }))
vi.mock('../../api/stockApi', () => ({ default: { getEmplacements: () => Promise.resolve({ data: [{ id: 3, nom: 'Camion 1' }] }) } }))

import AstreintesPage from './AstreintesPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AstreintesPage (WIR114)', () => {
  it('rend les 3 onglets et charge les astreintes', async () => {
    inst.getAstreintes.mockResolvedValue({ data: [{ id: 1, technicien: 10, technicien_nom: 'ahmed', date_debut: '2026-07-01', date_fin: '2026-07-07', telephone_astreinte: '0600' }] })
    render(<AstreintesPage />)
    expect(screen.getByRole('tab', { name: 'Astreintes' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Indisponibilités' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Récurrences' })).toBeInTheDocument()
    expect(await screen.findByTestId('astreinte-1')).toBeInTheDocument()
  })

  it('crée une astreinte via le dialogue', async () => {
    inst.getAstreintes.mockResolvedValue({ data: [] })
    const user = userEvent.setup()
    render(<AstreintesPage />)
    await waitFor(() => expect(inst.getAstreintes).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: /Nouvelle astreinte/ }))
    // Attend le technicien chargé.
    await screen.findByRole('option', { name: 'ahmed' })
    await user.selectOptions(screen.getByLabelText("Technicien d'astreinte"), '10')
    await user.type(screen.getByLabelText('Début'), '2026-08-01')
    await user.type(screen.getByLabelText('Fin'), '2026-08-07')
    await user.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(inst.createAstreinte).toHaveBeenCalledWith(
      expect.objectContaining({ technicien: 10, date_debut: '2026-08-01', date_fin: '2026-08-07' }),
    ))
  })
})
