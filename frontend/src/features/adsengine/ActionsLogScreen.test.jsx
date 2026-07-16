import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { filterActionLog, actionMode, actionResultKey } from './adsengine'

/* ENG28 — Journal d'actions : timeline EngineAction (raison, résultat, qui a
   approuvé, auto/manuel), filtrable par statut et par mode. */

const mocks = vi.hoisted(() => ({ log: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { actions: { log: mocks.log } },
}))

import ActionsLogScreen from './ActionsLogScreen'

const renderScreen = () => render(
  <MemoryRouter><ActionsLogScreen /></MemoryRouter>)

const LOG = [
  { id: 1, type: 'adjust_budget', reason_fr: 'CPL en baisse', statut: 'approuve', approuve_par: 'Reda', mode: 'manuel', created_at: '2026-07-10' },
  { id: 2, type: 'pause_campaign', reason_fr: 'Fréquence trop haute', statut: 'applique', auto: true, created_at: '2026-07-11' },
  { id: 3, type: 'swap_creative', reason_fr: 'Créatif fatigué', statut: 'rejete', approuve_par: 'Meryem', mode: 'manuel', created_at: '2026-07-12' },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.log.mockResolvedValue({ data: LOG })
})

describe('helpers de journal (purs)', () => {
  it('actionMode déduit auto vs manuel', () => {
    expect(actionMode({ auto: true })).toBe('auto')
    expect(actionMode({ mode: 'manuel' })).toBe('manuel')
    expect(actionMode({ approuve_par: 'Reda' })).toBe('manuel')
    expect(actionMode({})).toBe('auto')
  })
  it('actionResultKey normalise les variantes de statut', () => {
    expect(actionResultKey({ statut: 'approuvee' })).toBe('approuve')
    expect(actionResultKey({ statut: 'rejetée' })).toBe('rejete')
    expect(actionResultKey({ statut: 'pending' })).toBe('en_attente')
  })
  it('filterActionLog filtre par statut et par mode', () => {
    expect(filterActionLog(LOG, { statut: 'rejete' })).toHaveLength(1)
    expect(filterActionLog(LOG, { mode: 'auto' })).toHaveLength(1)
    expect(filterActionLog(LOG, { mode: 'manuel' })).toHaveLength(2)
  })
})

describe('ActionsLogScreen (ENG28)', () => {
  it('affiche la timeline avec résultat, qui a approuvé, et mode', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.log).toHaveBeenCalled())
    expect(screen.getAllByTestId('ae-log-row')).toHaveLength(3)
    expect(screen.getByText('Approuvée par Reda')).toBeInTheDocument()
    expect(screen.getAllByTestId('ae-log-result')[0]).toHaveTextContent('Approuvée')
    // L'action auto porte le badge Auto.
    expect(screen.getAllByTestId('ae-log-mode').some(el => el.textContent === 'Auto')).toBe(true)
  })

  it('filtrer par statut (rejetées) réduit la timeline', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.log).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('ae-log-filter-statut'), { target: { value: 'rejete' } })
    await waitFor(() => expect(screen.getAllByTestId('ae-log-row')).toHaveLength(1))
    expect(screen.getByText('Créatif fatigué')).toBeInTheDocument()
  })

  it('filtrer par mode (auto) réduit la timeline', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.log).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('ae-log-filter-mode'), { target: { value: 'auto' } })
    await waitFor(() => expect(screen.getAllByTestId('ae-log-row')).toHaveLength(1))
    expect(screen.getByText('Fréquence trop haute')).toBeInTheDocument()
  })
})
