import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(polyfillResizeObserver)

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
    deleteClasseur: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({ confirmDelete: vi.fn(() => Promise.resolve(true)) }),
}))

import reportingApi from '../../api/reportingApi'
import ClasseursListPage from './ClasseursListPage'
import { polyfillResizeObserver } from '../../test/selectNatif'

describe('ClasseursListPage (XPLT22)', () => {
  it('liste les classeurs existants', async () => {
    renderPage(<ClasseursListPage />)

    expect((await screen.findAllByText('Suivi CA')).length).toBeGreaterThan(0)
    await waitFor(() => expect(reportingApi.listClasseurs).toHaveBeenCalled())
  })

  // AERR130 — la relecture qui suit une suppression échoue : la ligne
  // supprimée part, l'autre reste, et l'écran le dit (jamais « Aucun classeur »).
  it('relecture rejetée après suppression : jamais « Aucun classeur »', async () => {
    reportingApi.listClasseurs.mockResolvedValueOnce({
      data: [{ id: 1, titre: 'Suivi CA', partage: true }, { id: 3, titre: 'Marge', partage: false }],
    })
    reportingApi.listClasseurs.mockRejectedValueOnce(new Error('Network Error'))
    renderPage(<ClasseursListPage />)
    await screen.findAllByText('Marge')
    await userEvent.click(screen.getAllByRole('button', { name: 'Supprimer' })[0])
    expect(await screen.findByText(/Liste pas à jour/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeTruthy()
    expect(screen.queryAllByText('Suivi CA')).toHaveLength(0)
    expect(screen.getAllByText('Marge').length).toBeGreaterThan(0)
    expect(screen.queryByText('Aucun classeur')).toBeNull()
  })
})
