import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT65 — Journal de chantier : une entrée/jour/chantier (unicité serveur),
   météo, effectif interne/sous-traitant, matériel, événements, visiteurs,
   export PDF. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { journalList, journalCreate, journalExportPdf } = vi.hoisted(() => ({
  journalList: vi.fn(),
  journalCreate: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  journalExportPdf: vi.fn(() => Promise.resolve({ data: new Blob(['pdf']) })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    journal: {
      list: (...args) => journalList(...args),
      create: (...args) => journalCreate(...args),
      exportPdf: (...args) => journalExportPdf(...args),
    },
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import JournalChantier from './JournalChantier'

beforeEach(() => {
  vi.clearAllMocks()
  journalList.mockResolvedValue({
    data: [
      {
        id: 1, chantier: 5, date: '2026-01-05', meteo: 'ensoleille',
        effectif_interne: { macon: 4 }, evenements: 'Coulage dalle',
      },
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

describe('JournalChantier (PACT65)', () => {
  it('affiche les entrées existantes', async () => {
    withProviders(<JournalChantier />)
    await waitFor(() => expect(screen.getAllByText('Coulage dalle').length).toBeGreaterThan(0))
    expect(screen.getAllByText('macon (4)').length).toBeGreaterThan(0)
  })

  it('enregistre une entrée avec effectif et un visiteur', async () => {
    const user = userEvent.setup()
    withProviders(<JournalChantier />)
    await waitFor(() => expect(screen.getAllByText('Coulage dalle').length).toBeGreaterThan(0))

    const sel_chantierOption = screen.getByLabelText("Chantier de l'entrée")
    await user.selectOptions(sel_chantierOption, within(sel_chantierOption).getByRole('option', { name: /Villa Zenith/ }))
    fireEvent.change(screen.getByLabelText("Date de l'entrée"), { target: { value: '2026-02-01' } })
    await user.selectOptions(screen.getByLabelText('Météo'), 'nuageux')

    await user.type(screen.getByLabelText('Métier (Effectif interne)'), 'électricien')
    await user.clear(screen.getByLabelText('Nombre (Effectif interne)'))
    await user.type(screen.getByLabelText('Nombre (Effectif interne)'), '2')
    await user.click(screen.getAllByRole('button', { name: 'Ajouter' })[0])
    expect(screen.getAllByText('électricien : 2').length).toBeGreaterThan(0)

    await user.type(screen.getByLabelText('Nom du visiteur'), 'Contrôleur ONEE')
    const boutonsAjouter = screen.getAllByRole('button', { name: 'Ajouter' })
    await user.click(boutonsAjouter[boutonsAjouter.length - 1])
    expect(screen.getAllByText(/Contrôleur ONEE/).length).toBeGreaterThan(0)

    await user.click(screen.getAllByRole('button', { name: "Enregistrer l'entrée" })[0])

    await waitFor(() => expect(journalCreate).toHaveBeenCalledWith(expect.objectContaining({
      chantier: '5',
      date: '2026-02-01',
      meteo: 'nuageux',
      effectif_interne: { électricien: 2 },
      visiteurs: [{ nom: 'Contrôleur ONEE', societe: '', motif: '' }],
    })))
  })

  it('exporte le journal en PDF pour le chantier filtré', async () => {
    const user = userEvent.setup()
    const createUrl = vi.fn(() => 'blob:mock')
    const revokeUrl = vi.fn()
    URL.createObjectURL = createUrl
    URL.revokeObjectURL = revokeUrl
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    withProviders(<JournalChantier />)
    await waitFor(() => expect(screen.getAllByText('Coulage dalle').length).toBeGreaterThan(0))

    const sel_chantierOption = screen.getByLabelText('Filtrer par chantier')
    await user.selectOptions(sel_chantierOption, within(sel_chantierOption).getByRole('option', { name: /Villa Zenith/ }))
    await user.click(screen.getAllByRole('button', { name: /Exporter PDF/ })[0])

    await waitFor(() => expect(journalExportPdf).toHaveBeenCalledWith(
      expect.objectContaining({ chantier: '5' }),
    ))
    expect(createUrl).toHaveBeenCalled()
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
  })
})
