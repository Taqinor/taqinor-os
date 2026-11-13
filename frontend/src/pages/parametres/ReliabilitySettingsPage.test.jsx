import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTOBS21 — écran /parametres/fiabilite-reglages : moitié frontend du
   singleton `core.ReliabilitySettings` (GET/PATCH `/core/fiabilite/reglages/`).
   Couvre : atteignable (route + nav), pré-remplissage, bascule d'un
   interrupteur puis PATCH du formulaire complet. */

const apiMock = vi.hoisted(() => ({
  getReliabilitySettings: vi.fn(),
  saveReliabilitySettings: vi.fn(),
}))
vi.mock('../../api/parametresApi', () => ({ default: apiMock }))

const toastError = vi.hoisted(() => vi.fn())
const toastSuccess = vi.hoisted(() => vi.fn())
vi.mock('../../ui/confirm', () => ({
  toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) },
}))

import ReliabilitySettingsPage from './ReliabilitySettingsPage'
import config from '../../features/parametres/module.config.jsx'

const REGLAGES = {
  notifier_maintenance_email: true,
  notifier_quota_email: true,
  notifier_incident_region: 'Casablanca',
  afficher_badge_sla_dashboard: true,
  updated_at: '2026-11-04T10:00:00Z',
}
const ENVOYE = {
  notifier_maintenance_email: true,
  notifier_quota_email: true,
  notifier_incident_region: 'Casablanca',
  afficher_badge_sla_dashboard: true,
}

beforeEach(() => {
  apiMock.getReliabilitySettings.mockReset().mockResolvedValue({ data: REGLAGES })
  apiMock.saveReliabilitySettings.mockReset().mockResolvedValue({ data: REGLAGES })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ReliabilitySettingsPage — NTOBS21', () => {
  it('est routée sous /parametres ET présente dans la nav', () => {
    const route = config.routes.find((r) => r.path === '/parametres/fiabilite-reglages')
    expect(route).toBeTruthy()
    const nav = config.nav.items.find((i) => i.to === '/parametres/fiabilite-reglages')
    expect(nav).toBeTruthy()
    expect(nav.roles).toEqual(route.roles)
  })

  it('charge et pré-remplit la région suivie', async () => {
    render(<ReliabilitySettingsPage />)
    expect(await screen.findByDisplayValue('Casablanca')).toBeInTheDocument()
    expect(apiMock.getReliabilitySettings).toHaveBeenCalledTimes(1)
  })

  it('couper les alertes de quota puis enregistrer envoie false', async () => {
    const user = userEvent.setup()
    render(<ReliabilitySettingsPage />)
    await screen.findByDisplayValue('Casablanca')
    await user.click(screen.getByLabelText('Prévenir des quotas'))
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(apiMock.saveReliabilitySettings).toHaveBeenCalledWith({
      ...ENVOYE, notifier_quota_email: false,
    }))
    expect(toastSuccess).toHaveBeenCalled()
  })

  it("un refus d'écriture s'affiche en erreur", async () => {
    apiMock.saveReliabilitySettings.mockRejectedValueOnce({
      response: { status: 403, data: { detail: 'Permission refusée.' } },
    })
    const user = userEvent.setup()
    render(<ReliabilitySettingsPage />)
    await screen.findByDisplayValue('Casablanca')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(toastError).toHaveBeenCalled())
  })
})

describe('ReliabilitySettingsPage — AERR56', () => {
  it('lecture rejetée : avis + Réessayer, aucun PATCH', async () => {
    const user = userEvent.setup()
    apiMock.getReliabilitySettings.mockReset().mockRejectedValueOnce(new Error('boom'))
    render(<ReliabilitySettingsPage />)
    expect(await screen.findByText(/Réglages non chargés/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Enregistrer/ })).toBeNull()
    expect(apiMock.saveReliabilitySettings).not.toHaveBeenCalled()
    apiMock.getReliabilitySettings.mockResolvedValue({ data: REGLAGES })
    await user.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByDisplayValue('Casablanca')).toBeInTheDocument()
  })
})
