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

/* XPLT22 — liste des classeurs (mini-spreadsheet BI). */

vi.mock('../../api/reportingApi', () => ({
  default: {
    listClasseurs: vi.fn(() => Promise.resolve({
      data: [{ id: 1, titre: 'Suivi CA', partage: true }],
    })),
    createClasseur: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  },
}))

import reportingApi from '../../api/reportingApi'
import ClasseursListPage from './ClasseursListPage'

describe('ClasseursListPage (XPLT22)', () => {
  it('liste les classeurs existants', async () => {
    renderPage(<ClasseursListPage />)

    expect((await screen.findAllByText('Suivi CA')).length).toBeGreaterThan(0)
    await waitFor(() => expect(reportingApi.listClasseurs).toHaveBeenCalled())
  })
})
