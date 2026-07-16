import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ENG43 — Écran Règles & anomalies : catalogue de gabarits FR (picker, jamais
   un builder libre), dry-run VISUALISÉ (objets touchés + effet), flux
   d'anomalies avec sévérités, historique des alertes. Objets/nombres = API
   ENG14/ENG16 mockée. */

const mocks = vi.hoisted(() => ({
  templates: vi.fn(),
  dryRun: vi.fn(),
  anomalies: vi.fn(),
  history: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    rules: { templates: mocks.templates, dryRun: mocks.dryRun },
    anomalies: { list: mocks.anomalies },
    alerts: { history: mocks.history },
  },
}))

import RulesScreen from './RulesScreen'

const renderScreen = () => render(<MemoryRouter><RulesScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.templates.mockResolvedValue({ data: [
    { key: 'overlap', nom: 'Anti-chevauchement d\'enchères',
      condition_fr: 'deux ad sets ciblent la même audience',
      action_fr: 'mettre en pause le moins performant' },
    { key: 'fatigue', nom: 'Fatigue créative',
      condition_fr: 'la fréquence dépasse 3', action_fr: 'proposer une rotation de créatif' },
  ] })
  mocks.dryRun.mockResolvedValue({ data: {
    resume_fr: '2 campagnes seraient touchées',
    objets_touches: [
      { id: 1, nom: 'Campagne Résidentiel', effet_fr: 'serait mise en pause' },
      { id: 2, nom: 'Campagne Pompage', effet_fr: 'inchangée' },
    ] } })
  mocks.anomalies.mockResolvedValue({ data: [
    { id: 9, titre: 'CPL en forte hausse', severite: 'critique',
      message: 'Le coût par lead a doublé en 24 h.', quand: '2026-07-15' },
  ] })
  mocks.history.mockResolvedValue({ data: { alerts: [
    { id: 1, niveau: 'alerte', message: 'Fréquence élevée', quand: '2026-07-12' },
  ] } })
})

describe('RulesScreen (ENG43)', () => {
  it('affiche le catalogue de gabarits en clair (condition FR → action FR)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.templates).toHaveBeenCalled())
    const cards = await screen.findAllByTestId('ae-rule-template')
    expect(cards.length).toBe(2)
    expect(cards[0]).toHaveTextContent('Anti-chevauchement')
    expect(cards[0]).toHaveTextContent('deux ad sets ciblent la même audience')
    expect(cards[0]).toHaveTextContent('mettre en pause le moins performant')
  })

  it('le dry-run est VISUALISÉ : objets touchés + effet de l\'API', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-rule-dryrun-overlap'))
    await waitFor(() => expect(mocks.dryRun).toHaveBeenCalledWith('overlap'))
    const result = await screen.findByTestId('ae-rule-dryrun-result-overlap')
    expect(result).toHaveTextContent('2 campagnes seraient touchées')
    expect(result).toHaveTextContent('Campagne Résidentiel')
    expect(result).toHaveTextContent('serait mise en pause')
    expect(screen.getAllByTestId('ae-rule-dryrun-object').length).toBe(2)
  })

  it('affiche le flux d\'anomalies avec leur sévérité', async () => {
    renderScreen()
    const anomaly = await screen.findByTestId('ae-anomaly')
    expect(anomaly).toHaveTextContent('CPL en forte hausse')
    expect(screen.getByTestId('ae-anomaly-severity')).toHaveTextContent('Critique')
  })

  it('affiche l\'historique des alertes', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-alert-history-row')).toHaveTextContent('Fréquence élevée')
  })
})
