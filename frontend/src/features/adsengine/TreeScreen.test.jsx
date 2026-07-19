import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ASG6 — L'Arbre : nœuds groupés par statut/fraîcheur, la file de priorité VoI
   (ASG3), et le drill-down nœud → tests (l'historique = "l'arbre à travers le
   temps") → leads réels derrière un test (dd-assumption-engine.md §3). Les
   chiffres affichés sont EXCLUSIVEMENT ceux de l'API mockée. */

const mocks = vi.hoisted(() => ({
  nodes: vi.fn(),
  queue: vi.fn(),
  tests: vi.fn(),
  testLeads: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    assumptions: {
      nodes: mocks.nodes, queue: mocks.queue, tests: mocks.tests, testLeads: mocks.testLeads,
    },
  },
}))

import TreeScreen from './TreeScreen'

const renderScreen = () => render(<MemoryRouter><TreeScreen /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.nodes.mockResolvedValue({ data: [
    { id: 11, enonce_fr: "Le hook « facture d'été » convertit mieux", classe: 'creatif',
      statut: 'validated', fraicheur_jours: 12 },
    { id: 12, enonce_fr: 'Le lookalike 1% sature à 30 j', classe: 'audience',
      statut: 'stale', fraicheur_jours: 190 },
  ] })
  mocks.queue.mockResolvedValue({ data: [
    { node_id: 12, enonce_fr: 'Le lookalike 1% sature à 30 j', voi: 0.42, rang: 1 },
    { node_id: 11, enonce_fr: "Le hook « facture d'été » convertit mieux", voi: 0.11, rang: 2 },
  ] })
  mocks.tests.mockResolvedValue({ data: [
    { id: 101, nom: 'Test hook facture vs neutre', verdict_display: 'Gagnant', quand: '2026-06-01' },
  ] })
  mocks.testLeads.mockResolvedValue({ data: [
    { id: 7, nom: 'Ahmed Benali', ville: 'Casablanca', stage_label: 'SIGNÉ' },
  ] })
})

describe('TreeScreen (ASG6)', () => {
  it('affiche les nœuds groupés par statut avec les chiffres de l\'API', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.nodes).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-tree-group-validated')).toBeInTheDocument()
    expect(screen.getByTestId('ae-tree-group-stale')).toBeInTheDocument()
    // L'énoncé apparaît DEUX fois (dans la file VoI et dans son groupe de statut) — attendu.
    expect(screen.getAllByText(/facture d'été/).length).toBeGreaterThan(0)
    expect(screen.getByText(/il y a 190 j/)).toBeInTheDocument()
  })

  it('affiche la file de priorité VoI ordonnée par rang avec les scores de l\'API', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.queue).toHaveBeenCalled())
    const table = await screen.findByTestId('ae-tree-queue-table')
    expect(table).toBeInTheDocument()
    expect(screen.getByTestId('ae-tree-queue-voi-12')).toHaveTextContent('0,42')
    expect(screen.getByTestId('ae-tree-queue-voi-11')).toHaveTextContent('0,11')
  })

  it('drill-down : cliquer un nœud charge et affiche ses tests passés', async () => {
    renderScreen()
    const toggle = await screen.findByTestId('ae-tree-node-toggle-11')
    fireEvent.click(toggle)
    await waitFor(() => expect(mocks.tests).toHaveBeenCalledWith(11))
    expect(await screen.findByTestId('ae-tree-test-101')).toHaveTextContent('Test hook facture vs neutre')
    expect(screen.getByTestId('ae-tree-test-101')).toHaveTextContent('Gagnant')
  })

  it('drill-down : cliquer un test charge et affiche les leads réels derrière', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-tree-node-toggle-11'))
    const testBtn = await screen.findByTestId('ae-tree-test-101')
    fireEvent.click(testBtn)
    await waitFor(() => expect(mocks.testLeads).toHaveBeenCalledWith(101))
    expect(await screen.findByTestId('ae-tree-lead-row')).toHaveTextContent('Ahmed Benali')
    expect(screen.getByTestId('ae-tree-lead-row')).toHaveTextContent('Casablanca')
  })

  it('affiche un état vide sans nœud ni file', async () => {
    mocks.nodes.mockResolvedValue({ data: [] })
    mocks.queue.mockResolvedValue({ data: [] })
    renderScreen()
    expect(await screen.findByTestId('ae-tree-empty')).toBeInTheDocument()
    expect(screen.getByTestId('ae-tree-queue-empty')).toBeInTheDocument()
  })
})
