import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* XKB1/ZCTR7-9 — La boîte d'approbations centralisée charge TOUTES les
   sources (aucun filtre `source=` par défaut), contrairement à la vue étroite
   de WorkflowsScreen (source=workflow uniquement). */

vi.mock('../../api/reportingApi', () => ({
  default: {
    approbationsEnAttente: vi.fn(() => Promise.resolve({
      data: {
        items: [
          {
            source: 'automation', id: 1, libelle: 'Règle X', demandeur: 'sami',
            priorite: null, anciennete_jours: 2, en_retard: false,
          },
          {
            source: 'installations', id: 7, libelle: 'Réquisition R-007',
            demandeur: null, priorite: 'haute', anciennete_jours: 5, en_retard: true,
          },
        ],
        total: 2,
      },
    })),
    deciderApprobation: vi.fn(() => Promise.resolve({ data: { detail: 'ok' } })),
    deciderApprobationsEnMasse: vi.fn(() => Promise.resolve({
      data: { resultats: [{ source: 'automation', id: 1, ok: true }] },
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import ApprobationsPage from './ApprobationsPage'

describe('ApprobationsPage (XKB1/ZCTR7-9 — boîte d’approbations centralisée)', () => {
  it('charge TOUTES les sources sans filtre par défaut', async () => {
    renderPage(<ApprobationsPage />)

    expect((await screen.findAllByText('Règle X')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Réquisition R-007').length).toBeGreaterThan(0)

    await waitFor(() => expect(reportingApi.approbationsEnAttente).toHaveBeenCalledWith({}))
  })

  it('affiche le badge « En retard » pour les items au-delà du SLA', async () => {
    renderPage(<ApprobationsPage />)
    expect(await screen.findAllByText('En retard')).not.toHaveLength(0)
  })

  it('approuver une ligne appelle deciderApprobation avec sa source/id', async () => {
    renderPage(<ApprobationsPage />)
    await screen.findAllByText('Règle X')

    const approveButtons = await screen.findAllByTestId('approbation-approve-automation-1')
    approveButtons[0].click()

    await waitFor(() => expect(reportingApi.deciderApprobation).toHaveBeenCalledWith(
      'automation', 1, 'approuver', '',
    ))
  })
})
