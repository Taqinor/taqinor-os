import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB48 — Cloche console : historique complet (résolues/reportées incluses),
   snooze par alerte, lien vers l'entité. Le lu/non-lu suit un horodatage
   localStorage (jamais l'API) — testé en le vidant à chaque cas. */

const mocks = vi.hoisted(() => ({
  history: vi.fn(),
  snooze: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    alerts: { history: mocks.history, snooze: mocks.snooze },
  },
}))

import AlertCenter from './AlertCenter'

const renderScreen = () => render(<MemoryRouter><AlertCenter /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  // Dates volontairement lointaines dans le passé : le test « ouvrir marque
  // tout lu » compare à `new Date()` RÉEL (pas de fake timers) — n'importe
  // quel horodatage d'exécution réel reste après 2020, jamais flaky.
  mocks.history.mockResolvedValue({ data: [
    { id: 1, message: 'CPL en forte hausse', severity: 'critical', resolved: false,
      snoozed_until: null, link: '/publicite/approbations', created_at: '2020-07-18T10:00:00Z' },
    { id: 2, message: 'Fréquence élevée', severity: 'warning', resolved: true,
      snoozed_until: null, link: '/publicite/regles', created_at: '2020-07-10T10:00:00Z' },
    { id: 3, message: 'Dépense en pause', severity: 'info', resolved: false,
      snoozed_until: '2099-01-01', link: '/publicite/regles', created_at: '2020-07-05T10:00:00Z' },
  ] })
  mocks.snooze.mockResolvedValue({ data: {} })
})

describe('AlertCenter (PUB48)', () => {
  it('affiche un badge de compteur avant la première ouverture', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.history).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-alert-center-badge')).toHaveTextContent('3')
  })

  it('ouvrir la cloche affiche l\'historique COMPLET (résolues + reportées incluses)', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-alert-center-toggle'))
    const items = await screen.findAllByTestId('ae-alert-center-item')
    expect(items.length).toBe(3)
    expect(items[1]).toHaveTextContent('Résolue')
    expect(items[2]).toHaveTextContent('Reportée')
  })

  it('ouvrir la cloche marque tout comme lu (le badge disparaît)', async () => {
    renderScreen()
    await screen.findByTestId('ae-alert-center-badge')
    fireEvent.click(screen.getByTestId('ae-alert-center-toggle'))
    await screen.findAllByTestId('ae-alert-center-item')
    fireEvent.click(screen.getByTestId('ae-alert-center-close'))
    expect(screen.queryByTestId('ae-alert-center-badge')).toBeNull()
  })

  it('chaque item porte un lien vers son entité', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-alert-center-toggle'))
    const link = await screen.findByTestId('ae-alert-center-link-1')
    expect(link).toHaveAttribute('href', '/publicite/approbations')
  })

  it('reporter une alerte active envoie la date choisie', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-alert-center-toggle'))
    fireEvent.click(await screen.findByTestId('ae-alert-center-snooze-1'))
    const dateInput = screen.getByTestId('ae-alert-center-snooze-date-1')
    fireEvent.change(dateInput, { target: { value: '2026-08-01' } })
    fireEvent.click(screen.getByTestId('ae-alert-center-snooze-confirm-1'))
    await waitFor(() => expect(mocks.snooze).toHaveBeenCalledWith(1, '2026-08-01'))
  })

  it('une alerte déjà reportée ou résolue n\'offre pas de bouton Reporter', async () => {
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-alert-center-toggle'))
    await screen.findAllByTestId('ae-alert-center-item')
    expect(screen.queryByTestId('ae-alert-center-snooze-2')).toBeNull()
    expect(screen.queryByTestId('ae-alert-center-snooze-3')).toBeNull()
  })

  it('un échec de report affiche une erreur', async () => {
    mocks.snooze.mockRejectedValue(new Error('500'))
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-alert-center-toggle'))
    fireEvent.click(await screen.findByTestId('ae-alert-center-snooze-1'))
    fireEvent.click(screen.getByTestId('ae-alert-center-snooze-confirm-1'))
    expect(await screen.findByTestId('ae-alert-center-err')).toBeInTheDocument()
  })

  it('aucune alerte affiche un état vide', async () => {
    mocks.history.mockResolvedValue({ data: [] })
    renderScreen()
    fireEvent.click(await screen.findByTestId('ae-alert-center-toggle'))
    expect(await screen.findByTestId('ae-alert-center-empty')).toBeInTheDocument()
  })
})
