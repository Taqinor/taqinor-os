import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB57 — Tuile Dashboard « score d'audit », auto-chargée + delta hebdo.
   Réutilise reporting/audit/ (déjà construit) — jamais un recalcul côté
   front, jamais un chiffre inventé. */

const mocks = vi.hoisted(() => ({
  audit: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    reports: { audit: mocks.audit },
  },
}))

import AuditScoreTile from './AuditScoreTile'

const renderTile = () => render(<MemoryRouter><AuditScoreTile /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AuditScoreTile (PUB57)', () => {
  it('se charge automatiquement au montage (sans clic)', async () => {
    mocks.audit.mockResolvedValue({ data: { score_tile: {
      score: 80, ok_count: 4, attention_count: 1, total_sections: 5, delta_hebdo: null,
    } } })
    renderTile()
    await waitFor(() => expect(mocks.audit).toHaveBeenCalled())
  })

  it('affiche le score + le nombre de sections OK', async () => {
    mocks.audit.mockResolvedValue({ data: { score_tile: {
      score: 80, ok_count: 4, attention_count: 1, total_sections: 5, delta_hebdo: null,
    } } })
    renderTile()
    expect(await screen.findByTestId('ae-audit-score-tile-value')).toHaveTextContent('80/100')
    expect(screen.getByText('4/5 sections OK — voir le détail →')).toBeInTheDocument()
  })

  it('affiche un delta hebdo positif en vert avec le signe +', async () => {
    mocks.audit.mockResolvedValue({ data: { score_tile: {
      score: 80, ok_count: 4, attention_count: 1, total_sections: 5, delta_hebdo: 20,
    } } })
    renderTile()
    const delta = await screen.findByTestId('ae-audit-score-tile-delta')
    expect(delta).toHaveTextContent('+20 vs il y a 7 j')
  })

  it('affiche un delta hebdo négatif sans signe +', async () => {
    mocks.audit.mockResolvedValue({ data: { score_tile: {
      score: 40, ok_count: 2, attention_count: 3, total_sections: 5, delta_hebdo: -20,
    } } })
    renderTile()
    const delta = await screen.findByTestId('ae-audit-score-tile-delta')
    expect(delta).toHaveTextContent('-20 vs il y a 7 j')
  })

  it('sans historique (premier calcul), aucun delta n\'est affiché', async () => {
    mocks.audit.mockResolvedValue({ data: { score_tile: {
      score: 80, ok_count: 4, attention_count: 1, total_sections: 5, delta_hebdo: null,
    } } })
    renderTile()
    await screen.findByTestId('ae-audit-score-tile-value')
    expect(screen.queryByTestId('ae-audit-score-tile-delta')).toBeNull()
  })

  it('sans section évaluable, affiche un tiret plutôt qu\'un chiffre inventé', async () => {
    mocks.audit.mockResolvedValue({ data: { score_tile: {
      score: null, ok_count: 0, attention_count: 0, total_sections: 0, delta_hebdo: null,
    } } })
    renderTile()
    expect(await screen.findByTestId('ae-audit-score-tile-value')).toHaveTextContent('—')
  })

  it('un échec réseau affiche un état dégradé, jamais un crash', async () => {
    mocks.audit.mockRejectedValue(new Error('500'))
    renderTile()
    expect(await screen.findByTestId('ae-audit-score-tile-error')).toBeInTheDocument()
  })

  it('la tuile est un lien vers Reporting (le détail des 5 sections)', async () => {
    mocks.audit.mockResolvedValue({ data: { score_tile: {
      score: 80, ok_count: 4, attention_count: 1, total_sections: 5, delta_hebdo: null,
    } } })
    renderTile()
    const tile = await screen.findByTestId('ae-audit-score-tile')
    expect(tile).toHaveAttribute('href', '/publicite/reporting')
  })
})
