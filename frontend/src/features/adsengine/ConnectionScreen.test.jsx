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
  // PUB9 — les VRAIS champs sérialisés (avant cette tâche, l'écran + ce test
  // mockaient des clés qui n'existaient PAS côté modèle : max_daily_budget_mad
  // (au lieu de daily_budget_ceiling_mad) et require_approval_above_mad
  // (aucun champ de ce nom n'existe) — les garde-fous ne s'enregistraient
  // donc JAMAIS réellement, DRF ignorant silencieusement un champ inconnu).
  mocks.guardGet.mockResolvedValue({ data: {
    daily_budget_ceiling_mad: 100, monthly_budget_ceiling_mad: 2000,
    weekly_change_pct_max: 20, anomaly_window_hours: 48,
    auto_rotate_creative: false, auto_rebalance_within_band: false,
    pacing_band_pct: 15, exploration_floor_mad: 20, exploration_floor_pct: 20,
    health_creative_weight_ctr: 60, health_creative_weight_freshness: 40,
    health_ops_weight_cpl: 60, health_ops_weight_delivery: 40,
  } })
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

  it('PUB9 — édition du plafond quotidien (vraie clé serializer) → guardrail.update', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.guardGet).toHaveBeenCalled())
    const daily = await screen.findByTestId('ae-conn-guard-daily_budget_ceiling_mad')
    expect(daily.value).toBe('100')
    fireEvent.change(daily, { target: { value: '150' } })
    fireEvent.click(screen.getByTestId('ae-conn-guard-save'))
    await waitFor(() => expect(mocks.guardUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ daily_budget_ceiling_mad: 150 })))
  })

  it('PUB9 — chaque champ sérialisé de GuardrailConfig est éditable (13 champs, groupés)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.guardGet).toHaveBeenCalled())
    const keys = [
      'daily_budget_ceiling_mad', 'monthly_budget_ceiling_mad', 'weekly_change_pct_max',
      'anomaly_window_hours', 'auto_rotate_creative', 'auto_rebalance_within_band',
      'pacing_band_pct', 'exploration_floor_mad', 'exploration_floor_pct',
      'health_creative_weight_ctr', 'health_creative_weight_freshness',
      'health_ops_weight_cpl', 'health_ops_weight_delivery',
    ]
    for (const key of keys) {
      expect(await screen.findByTestId(`ae-conn-guard-${key}`)).toBeInTheDocument()
    }
  })

  it('PUB9 — les bascules auto-application (ENG8) s\'éditent et s\'envoient explicitement', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.guardGet).toHaveBeenCalled())
    const autoRotate = await screen.findByTestId('ae-conn-guard-auto_rotate_creative')
    expect(autoRotate.checked).toBe(false)
    fireEvent.click(autoRotate)
    expect(autoRotate.checked).toBe(true)
    fireEvent.click(screen.getByTestId('ae-conn-guard-save'))
    await waitFor(() => expect(mocks.guardUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        auto_rotate_creative: true, auto_rebalance_within_band: false,
      })))
  })

  it('chaque champ de garde-fou porte une aide FR', async () => {
    renderScreen()
    await screen.findByTestId('ae-conn-guard-daily_budget_ceiling_mad')
    expect(screen.getByText(/détecteur d'anomalie compare la dépense/)).toBeInTheDocument()
    expect(screen.getByText(/bande de pacing ci-dessous/)).toBeInTheDocument()
  })

  it('AUCUN toggle d\'activation de campagne n\'existe à l\'écran (par design)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    expect(screen.queryByRole('switch')).toBeNull()
    expect(screen.queryByText(/activer la campagne/i)).toBeNull()
    // Seules les 2 bascules d'auto-application (ENG8) existent — jamais une
    // activation de campagne Meta (interdite en dur côté service, pas un
    // réglage écran).
    expect(screen.getAllByRole('checkbox')).toHaveLength(2)
  })
})
