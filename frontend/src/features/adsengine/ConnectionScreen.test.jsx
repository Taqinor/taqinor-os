import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG22 — l'écran Connexion : identifiants WRITE-ONLY (jamais relus), statuts
   de câblage (ENG12), édition plafond/band, et AUCUN toggle d'activation
   (le client naît PAUSED, par design). API entièrement mockée. */

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  save: vi.fn(),
  health: vi.fn(),
  guardGet: vi.fn(),
  guardUpdate: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    connection: { get: mocks.get, save: mocks.save, health: mocks.health },
    guardrail: { get: mocks.guardGet, update: mocks.guardUpdate },
  },
}))

import ConnectionScreen from './ConnectionScreen'

const renderScreen = () => render(
  <MemoryRouter><ConnectionScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  // Le serveur ne renvoie qu'un STATUT — jamais un secret.
  mocks.get.mockResolvedValue({ data: { connected: true, ad_account_id_masque: '***4321' } })
  mocks.health.mockResolvedValue({ data: { statuses: [
    { key: 'token', ok: true },
    { key: 'ad_account', ok: true },
    { key: 'pixel', ok: false, detail: 'Non configuré' },
    { key: 'paused', ok: true },
  ] } })
  mocks.guardGet.mockResolvedValue({ data: {
    max_daily_budget_mad: 100, max_monthly_budget_mad: 2000,
    require_approval_above_mad: 50 } })
  mocks.save.mockResolvedValue({ data: {} })
  mocks.guardUpdate.mockResolvedValue({ data: {} })
})

describe('ConnectionScreen (ENG22)', () => {
  it('les champs secrets partent vides et le serveur n\'en relit aucun', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    // Même avec un statut « connecté », le secret n'est jamais réaffiché.
    expect(screen.getByTestId('ae-conn-cred-app_secret').value).toBe('')
    expect(screen.getByTestId('ae-conn-cred-access_token').value).toBe('')
    // Le statut masqué s'affiche (jamais le secret complet).
    expect(await screen.findByText(/\*\*\*4321/)).toBeInTheDocument()
  })

  it('parcours setup complet : saisie → enregistrement (write-only)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('ae-conn-cred-app_id'),
      { target: { value: '123456' } })
    fireEvent.change(screen.getByTestId('ae-conn-cred-app_secret'),
      { target: { value: 's3cr3t' } })
    fireEvent.change(screen.getByTestId('ae-conn-cred-ad_account_id'),
      { target: { value: 'act_999' } })
    fireEvent.click(screen.getByTestId('ae-conn-cred-save'))
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith({
      app_id: '123456', app_secret: 's3cr3t', ad_account_id: 'act_999' }))
    // Après enregistrement, les champs sont RE-vidés (aucun secret en mémoire).
    await waitFor(() =>
      expect(screen.getByTestId('ae-conn-cred-app_secret').value).toBe(''))
    expect(await screen.findByTestId('ae-conn-msg')).toBeInTheDocument()
  })

  it('les statuts de câblage (ENG12) sont rendus avec OK / À configurer', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-conn-health-token')).toBeInTheDocument()
    const pixel = screen.getByTestId('ae-conn-health-pixel')
    expect(pixel).toHaveTextContent('À configurer')
    expect(pixel).toHaveTextContent('Non configuré')
    expect(screen.getByTestId('ae-conn-health-token')).toHaveTextContent('OK')
  })

  it('édition du plafond/band → guardrail.update avec des nombres', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.guardGet).toHaveBeenCalled())
    const daily = await screen.findByTestId('ae-conn-guard-max_daily_budget_mad')
    expect(daily.value).toBe('100')
    fireEvent.change(daily, { target: { value: '150' } })
    fireEvent.change(screen.getByTestId('ae-conn-guard-require_approval_above_mad'),
      { target: { value: '75' } })
    fireEvent.click(screen.getByTestId('ae-conn-guard-save'))
    await waitFor(() => expect(mocks.guardUpdate).toHaveBeenCalledWith({
      max_daily_budget_mad: 150, max_monthly_budget_mad: 2000,
      require_approval_above_mad: 75 }))
  })

  it('AUCUN toggle/switch/case d\'activation n\'existe à l\'écran (par design)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    expect(screen.queryByRole('switch')).toBeNull()
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByText(/activer/i)).toBeNull()
  })
})
