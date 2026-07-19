import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* WIR137 — la cloche « Mes tâches de fond » interroge core/jobs-status/, se
   masque tant qu'aucun job n'existe, affiche un badge du nombre de jobs actifs,
   et liste progression + état de fin dans son popover. */

const { list } = vi.hoisted(() => ({ list: vi.fn() }))
vi.mock('../../api/coreApi', () => ({
  default: { jobsStatus: { list } },
}))
// Sonde une fois au montage (pas de timers réels en test).
vi.mock('../../hooks/useVisibilityAwarePolling', () => ({
  default: (tasks) => { tasks.forEach((t) => t.fn()); return { resume: () => {} } },
}))

import BackgroundJobsBell from './BackgroundJobsBell'

beforeEach(() => { list.mockReset() })
afterEach(() => cleanup())

describe('WIR137 BackgroundJobsBell', () => {
  it('reste masquée quand aucun job n’existe', async () => {
    list.mockResolvedValue({ data: { results: [] } })
    render(<BackgroundJobsBell />)
    await waitFor(() => expect(list).toHaveBeenCalled())
    expect(screen.queryByTestId('bg-jobs-bell')).not.toBeInTheDocument()
  })

  it('affiche le badge des jobs actifs et la liste dans le popover', async () => {
    list.mockResolvedValue({
      data: {
        results: [
          { id: 1, kind: 'Export factures', statut: 'running', progress_pct: 40 },
          { id: 2, kind: 'Import clients', statut: 'done', progress_pct: 100 },
          { id: 3, kind: 'Export stock', statut: 'failed', message_erreur: 'Timeout' },
        ],
      },
    })
    render(<BackgroundJobsBell />)
    const bell = await screen.findByTestId('bg-jobs-bell')
    // Un seul job actif (running) → badge « 1 ».
    expect(bell).toHaveTextContent('1')
    fireEvent.click(bell)
    expect(await screen.findByText('Export factures')).toBeInTheDocument()
    expect(screen.getByText('Import clients')).toBeInTheDocument()
    expect(screen.getByText('Timeout')).toBeInTheDocument()
    // La barre de progression du job en cours porte sa valeur.
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '40')
  })
})
