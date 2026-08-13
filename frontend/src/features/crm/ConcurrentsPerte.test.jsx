import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT103 — Concurrents sur affaires perdues : le concurrent saisi apparaît
   dans l'analyse par lead perdu, sans dupliquer une saisie déjà faite côté
   litiges (dette distincte, hors périmètre de cet écran). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { getLeads, getConcurrentsPerte, createConcurrentPerte } = vi.hoisted(() => ({
  getLeads: vi.fn(),
  getConcurrentsPerte: vi.fn(),
  createConcurrentPerte: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getLeads: (...args) => getLeads(...args),
    getConcurrentsPerte: (...args) => getConcurrentsPerte(...args),
    createConcurrentPerte: (...args) => createConcurrentPerte(...args),
  },
}))

import ConcurrentsPerte from './ConcurrentsPerte'

beforeEach(() => {
  vi.clearAllMocks()
  getLeads.mockResolvedValue({
    data: [
      { id: 42, nom: 'Ahmed Alami', societe: 'Villa Palmeraie', perdu: true },
      { id: 43, nom: 'Sara B.', societe: 'En cours', perdu: false },
    ],
  })
  getConcurrentsPerte.mockResolvedValue({
    data: [
      { id: 1, concurrent_nom: 'SunTech', concurrent_prix: '85000.00', devise: 'MAD', motif: 'Prix', saisi_par_nom: 'meryem' },
    ],
  })
})

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ConcurrentsPerte (PACT103)', () => {
  it('ne montre que les leads réellement perdus dans la recherche', async () => {
    const user = userEvent.setup()
    withProviders(<ConcurrentsPerte />)

    await user.type(screen.getByLabelText('Rechercher un lead perdu'), 'Alami')
    await waitFor(() => expect(getLeads).toHaveBeenCalledWith({ search: 'Alami' }))

    expect((await screen.findAllByText(/Ahmed Alami/)).length).toBeGreaterThan(0)
    expect(screen.queryByText(/Sara B\./)).not.toBeInTheDocument()
  })

  it('affiche l’analyse concurrentielle du lead choisi', async () => {
    const user = userEvent.setup()
    withProviders(<ConcurrentsPerte />)

    await user.type(screen.getByLabelText('Rechercher un lead perdu'), 'Alami')
    const bouton = (await screen.findAllByRole('button', { name: /Ahmed Alami/ }))[0]
    await user.click(bouton)

    await waitFor(() => expect(getConcurrentsPerte).toHaveBeenCalledWith({ lead: 42 }))
    expect((await screen.findAllByText('SunTech')).length).toBeGreaterThan(0)
  })

  it('enregistre un nouveau concurrent sur le lead sélectionné', async () => {
    const user = userEvent.setup()
    withProviders(<ConcurrentsPerte />)

    await user.type(screen.getByLabelText('Rechercher un lead perdu'), 'Alami')
    const bouton = (await screen.findAllByRole('button', { name: /Ahmed Alami/ }))[0]
    await user.click(bouton)
    await screen.findAllByText('SunTech')

    await user.type(screen.getByLabelText('Concurrent gagnant'), 'GreenSolar')
    await user.type(screen.getByLabelText('Prix du concurrent'), '79000')
    await user.click(screen.getAllByRole('button', { name: 'Enregistrer' })[0])

    await waitFor(() => expect(createConcurrentPerte).toHaveBeenCalledWith(expect.objectContaining({
      lead: 42, concurrent_nom: 'GreenSolar', concurrent_prix: '79000',
    })))
  })
})
