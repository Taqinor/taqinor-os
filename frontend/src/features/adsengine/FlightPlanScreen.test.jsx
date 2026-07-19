import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG40 — Éditeur de plan de vol + préflight (écran-amiral P7) : composer les
   phases depuis un gabarit, préflight ADSENG38 en checklist verte/rouge FR,
   validation qui passe OU refuse avec raisons, simulation lançable. Toutes les
   raisons/portes = celles de l'API mockée (ADSENG28/38). */

const mocks = vi.hoisted(() => ({
  templates: vi.fn(),
  backlogArms: vi.fn(),
  preflight: vi.fn(),
  validate: vi.fn(),
  simulate: vi.fn(),
  engagementPresets: vi.fn(),
  createEngagement: vi.fn(),
  deliveryEstimate: vi.fn(),
  // PUB10 — pleines permissions par défaut ; restreintes dans les tests dédiés.
  permissions: ['adsengine_manage'],
}))

vi.mock('./adsengineApi', () => ({
  default: {
    flightplan: {
      templates: mocks.templates,
      backlogArms: mocks.backlogArms,
      preflight: mocks.preflight,
      validate: mocks.validate,
      simulate: mocks.simulate,
    },
    // PUB5 — EngagementAudiencePicker mounted in the compose column.
    audiences: {
      engagementPresets: mocks.engagementPresets,
      createEngagement: mocks.createEngagement,
      deliveryEstimate: mocks.deliveryEstimate,
    },
  },
}))

vi.mock('./useAdsPermissions', () => ({
  useAdsPermissions: () => ({
    loading: false,
    has: (code) => mocks.permissions.includes(code),
  }),
}))

import FlightPlanScreen from './FlightPlanScreen'

const renderScreen = () => render(<MemoryRouter><FlightPlanScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.templates.mockResolvedValue({ data: [
    { key: 'lancement', nom: 'Lancement solaire 6 mois', phases: [
      { key: 'amorce', label: 'Amorçage', duree_mois: 1 },
      { key: 'montee', label: 'Montée en charge', duree_mois: 2 },
      { key: 'croisiere', label: 'Croisière', duree_mois: 3 },
    ] },
  ] })
  mocks.backlogArms.mockResolvedValue({ data: [
    { id: 1, nom: 'Reel toiture' }, { id: 2, nom: 'Statique pompe' },
  ] })
  mocks.preflight.mockResolvedValue({ data: { pret: false, portes: [
    { key: 'loop', label: 'Signal du loop (ENG12)', ok: true },
    { key: 'garde_fous', label: 'Garde-fous posés', ok: true },
    { key: 'backlog', label: 'Backlog volume + diversité', ok: false, detail: 'Runway sous 7 jours.' },
    { key: 'simulation', label: 'Simulation verte', ok: false, detail: 'Aucune simulation lancée.' },
  ] } })
  mocks.engagementPresets.mockResolvedValue({ data: { presets: [
    { key: 'lead_submitted', label: 'Formulaire soumis', source_type: 'lead', retention_days: 90 },
  ] } })
  mocks.createEngagement.mockResolvedValue({ data: { preset: 'lead_submitted', audience_id: '901', retention_days: 90 } })
  mocks.deliveryEstimate.mockResolvedValue({ data: { estimate: { estimate_ready: true, estimate_dau: 8000 } } })
  mocks.permissions = ['adsengine_manage']
})

describe('FlightPlanScreen (ENG40)', () => {
  it('compose les phases 6 mois depuis un gabarit', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.templates).toHaveBeenCalled())
    fireEvent.change(await screen.findByTestId('ae-fp-template'), { target: { value: 'lancement' } })
    const phases = await screen.findByTestId('ae-fp-phases')
    expect(phases).toHaveTextContent('Amorçage')
    expect(phases).toHaveTextContent('Croisière')
    expect(screen.getAllByTestId('ae-fp-phase').length).toBe(3)
  })

  it('affiche le préflight ADSENG38 en checklist verte/rouge FR', async () => {
    renderScreen()
    const pf = await screen.findByTestId('ae-fp-preflight')
    expect(pf).toHaveTextContent('Signal du loop (ENG12)')
    expect(pf).toHaveTextContent('Runway sous 7 jours.')
    // 2 portes rouges → verdict « bloquée ».
    expect(screen.getByTestId('ae-fp-preflight-verdict')).toHaveTextContent('bloquée')
    expect(screen.getAllByTestId('ae-fp-gate-ok').length).toBe(2)
    expect(screen.getAllByTestId('ae-fp-gate-ko').length).toBe(2)
  })

  it('valide un plan composé (feu vert)', async () => {
    mocks.validate.mockResolvedValue({ data: { ok: true, raisons: [] } })
    renderScreen()
    fireEvent.change(await screen.findByTestId('ae-fp-template'), { target: { value: 'lancement' } })
    fireEvent.click(await screen.findByTestId('ae-fp-validate'))
    expect(await screen.findByTestId('ae-fp-valid')).toHaveTextContent('Plan valide')
    expect(mocks.validate).toHaveBeenCalled()
  })

  it('refuse un plan avec les raisons FR de l\'API', async () => {
    mocks.validate.mockResolvedValue({ data: { ok: false, raisons: [
      'Le budget mensuel dépasse le plafond des garde-fous.',
      'Aucun bras sélectionné.',
    ] } })
    renderScreen()
    fireEvent.change(await screen.findByTestId('ae-fp-template'), { target: { value: 'lancement' } })
    fireEvent.click(await screen.findByTestId('ae-fp-validate'))
    const refusal = await screen.findByTestId('ae-fp-refusal')
    expect(refusal).toHaveTextContent('Plan refusé')
    expect(refusal).toHaveTextContent('Le budget mensuel dépasse le plafond des garde-fous.')
    expect(screen.getAllByTestId('ae-fp-refusal-reason').length).toBe(2)
  })

  it('lance la simulation depuis l\'écran', async () => {
    mocks.simulate.mockResolvedValue({ data: { id: 9 } })
    renderScreen()
    fireEvent.change(await screen.findByTestId('ae-fp-template'), { target: { value: 'lancement' } })
    fireEvent.click(await screen.findByTestId('ae-fp-simulate'))
    await waitFor(() => expect(mocks.simulate).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-fp-sim-msg')).toHaveTextContent('Simulation lancée')
  })

  it('sélectionne des bras depuis le backlog', async () => {
    renderScreen()
    const arm = await screen.findByTestId('ae-fp-arm-1')
    fireEvent.click(arm)
    expect(arm).toBeChecked()
  })

  describe('PUB5 — Audiences d\'engagement dans le composeur', () => {
    it('monte le picker et estime l\'audience AVEC le ciblage MA de base', async () => {
      renderScreen()
      await screen.findByTestId('ae-fp-audiences')
      expect(await screen.findByTestId('ae-engagement-option-lead_submitted')).toBeInTheDocument()
      fireEvent.click(screen.getByTestId('ae-engagement-estimate-btn'))
      await waitFor(() => expect(mocks.deliveryEstimate).toHaveBeenCalledWith({
        targeting_spec: { geo_locations: { countries: ['MA'] } },
      }))
      expect(await screen.findByTestId('ae-engagement-estimate')).toHaveTextContent('8000')
    })

    it('créer une audience l\'ajoute comme variable du plan', async () => {
      renderScreen()
      await screen.findByTestId('ae-fp-audiences')
      fireEvent.click(await screen.findByTestId('ae-engagement-option-lead_submitted'))
      fireEvent.click(screen.getByTestId('ae-engagement-create-btn'))
      await waitFor(() => expect(mocks.createEngagement).toHaveBeenCalled())
      // Le plan démarre avec 1 variable vide ; la création en ajoute une 2ᵉ
      // (index 1) pré-remplie avec l'id de l'audience créée.
      await waitFor(() =>
        expect(screen.getByTestId('ae-fp-var-cle-1').value).toBe('audience_engagement'))
      expect(screen.getByTestId('ae-fp-var-val-1').value).toBe('901')
    })
  })

  describe('PUB10 — Valider/Simuler exigent adsengine_manage', () => {
    it('sans adsengine_manage, Valider et Simuler sont grisés', async () => {
      mocks.permissions = []
      renderScreen()
      fireEvent.change(await screen.findByTestId('ae-fp-template'), { target: { value: 'lancement' } })
      expect(screen.getByTestId('ae-fp-validate')).toBeDisabled()
      expect(screen.getByTestId('ae-fp-simulate')).toBeDisabled()
      fireEvent.click(screen.getByTestId('ae-fp-validate'))
      expect(mocks.validate).not.toHaveBeenCalled()
    })
  })
})
