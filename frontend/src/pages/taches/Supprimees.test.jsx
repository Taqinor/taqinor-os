import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import Supprimees from './Supprimees'

const api = vi.hoisted(() => ({
  listerSupprimees: vi.fn(), listerGestes: vi.fn(), annulerGeste: vi.fn(), restaurerProjet: vi.fn(), restaurerTache: vi.fn(),
}))
vi.mock('../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))

/* R2-125 — « Supprimées récemment » + « Derniers gestes » : chaque geste dit la tâche qu'il a touchée
   (`gestes.json` : `titre`), un squelette tient la place pendant la lecture, la liste ne se vide jamais
   sur une lecture en échec. Réponses = `gestes.json` et `supprimees.json`. */

const AUJOURD = '2026-11-17'
const gestes = () => structuredClone(exempleContrat('taches', 'gestes'))
const supprimees = () => structuredClone(exempleContrat('taches', 'supprimees'))
const vide = { projets: [], taches: [] }

const monter = () => render(<MemoryRouter><Supprimees aujourdhui={AUJOURD} /></MemoryRouter>)

beforeEach(() => {
  api.listerSupprimees.mockResolvedValue({ data: supprimees() })
  api.listerGestes.mockResolvedValue({ data: gestes() })
  api.annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
})
afterEach(() => { vi.clearAllMocks(); vi.useRealTimers(); reinitialiserGestes() })

describe('R2-125 — Supprimées récemment et derniers gestes', () => {
  it('chaque geste dit la tâche touchée : « 09:20 Reportée à jeu. 19 · Appeler le fournisseur · Annuler »', async () => {
    monter()
    const section = await screen.findByRole('region', { name: 'Derniers gestes' })
    const rangees = within(section).getAllByRole('listitem')
    expect(rangees).toHaveLength(2)
    expect(rangees[0]).toHaveTextContent('Reportée à jeu. 19 · Appeler le fournisseur')
    expect(within(rangees[0]).getByRole('button', { name: 'Annuler : Reportée à jeu. 19 · Appeler le fournisseur' })).toBeInTheDocument()
  })

  it('un geste sans tâche (le rythme) garde son message seul', async () => {
    monter()
    const section = await screen.findByRole('region', { name: 'Derniers gestes' })
    const rythme = within(section).getAllByRole('listitem')[1]
    expect(rythme).toHaveTextContent('Garder ce rythme : environ 5 tâches par jour (4 à 6).')
    expect(rythme).not.toHaveTextContent(' · ')
  })

  it('Annuler envoie l\'identifiant du geste', async () => {
    monter()
    const section = await screen.findByRole('region', { name: 'Derniers gestes' })
    await userEvent.click(within(section).getByRole('button', { name: /^Annuler : Reportée/ }))
    expect(api.annulerGeste).toHaveBeenCalledWith(77)
    await waitFor(() => expect(api.listerGestes).toHaveBeenCalledTimes(2))
  })

  it('un squelette « Chargement » tient la place après 1 s, jamais « Rien de supprimé » avant la réponse', async () => {
    vi.useFakeTimers()
    let repondre
    api.listerSupprimees.mockReturnValue(new Promise((resolve) => { repondre = resolve }))
    api.listerGestes.mockReturnValue(new Promise(() => {}))
    monter()
    expect(screen.queryByText('Rien de supprimé')).toBeNull()
    await act(async () => { await vi.advanceTimersByTimeAsync(1100) })
    expect(screen.getByRole('status', { name: 'Chargement' })).toBeInTheDocument()
    expect(screen.queryByText('Rien de supprimé')).toBeNull()
    api.listerGestes.mockResolvedValue({ data: { results: [] } })
    await act(async () => { repondre({ data: vide }) })
  })

  it('une lecture en échec ne vide pas ce qui est affiché', async () => {
    monter()
    await screen.findByRole('region', { name: 'Derniers gestes' })
    api.listerSupprimees.mockRejectedValue(new Error('Network Error'))
    await userEvent.click(within(screen.getByRole('region', { name: 'Derniers gestes' })).getByRole('button', { name: /^Annuler : Reportée/ }))
    await screen.findByRole('alert')
    expect(screen.getByRole('region', { name: 'Derniers gestes' })).toBeInTheDocument()
  })
})
