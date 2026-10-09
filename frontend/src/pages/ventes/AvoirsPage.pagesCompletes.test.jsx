import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* AFAC63 — le compteur d'avoirs lit TOUTES les pages de /avoirs/ (55 avoirs,
   50 par page, forme DRF réelle {count, next, results}). */

vi.mock('../../hooks/useHasPermission', () => ({ useIsAdmin: () => false }))

const TOUS = Array.from({ length: 55 }, (_, i) => ({
  id: i + 1, reference: `AV-${i + 1}`, statut: 'emise', total_ttc: '100.00',
}))

vi.mock('../../api/ventesApi', () => ({
  default: {
    getAvoirs: vi.fn((params = {}) => {
      const page = params.page || 1
      const results = TOUS.slice((page - 1) * 50, page * 50)
      return Promise.resolve({
        data: { count: TOUS.length, next: page * 50 < TOUS.length ? 'x' : null, results },
      })
    }),
    annulerAvoir: vi.fn(),
    telechargerAvoirPdf: vi.fn(),
  },
}))

import AvoirsPage from './AvoirsPage'

describe('AvoirsPage — AFAC63 : toutes les pages', () => {
  it('le compteur affiche 55, pas 50', async () => {
    render(<MemoryRouter><AvoirsPage /></MemoryRouter>)
    expect(await screen.findByText('55')).toBeInTheDocument()
  })
})
