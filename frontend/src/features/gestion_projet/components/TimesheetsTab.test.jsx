import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import TimesheetsTab from './TimesheetsTab'

/* XPRJ7-8/ZPRJ5-6 — Workflow d'approbation des timesheets : soumettre (depuis
   brouillon) / approuver / rejeter (depuis soumise), toujours via les actions
   serveur dédiées (jamais un PATCH statut direct). */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    soumettreTimesheet: vi.fn(() => Promise.resolve({ data: {} })),
    approuverTimesheet: vi.fn(() => Promise.resolve({ data: {} })),
    rejeterTimesheet: vi.fn(() => Promise.resolve({ data: {} })),
    getTempsManquants: vi.fn(() => Promise.resolve({ data: { lignes: [] } })),
    getClassementTemps: vi.fn(() => Promise.resolve({ data: { lignes: [] } })),
    getRapprochementTemps: vi.fn(() => Promise.resolve({ data: { ecarts: [] } })),
    getRapportTemps: vi.fn(() => Promise.resolve({ data: { lignes: [], total_heures: '0', total_heures_facturables: '0' } })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

const timesheets = [
  { id: 1, date: '2026-07-01', projet_code: 'P-1', ressource_nom: 'Amine', heures: '4', cout: '400', statut: 'brouillon' },
  { id: 2, date: '2026-07-02', projet_code: 'P-1', ressource_nom: 'Amine', heures: '3', cout: '300', statut: 'soumise' },
]

describe('TimesheetsTab', () => {
  it('affiche les lignes avec leur statut', async () => {
    render(<TimesheetsTab timesheets={timesheets} onChanged={vi.fn()} />)
    expect(await screen.findByText('Brouillon')).toBeInTheDocument()
    expect(screen.getByText('Soumise')).toBeInTheDocument()
  })

  it('« Soumettre » sur une ligne brouillon appelle l\'action serveur dédiée', async () => {
    const onChanged = vi.fn()
    const user = userEvent.setup()
    const { container } = render(<TimesheetsTab timesheets={timesheets} onChanged={onChanged} />)
    await screen.findByText('Brouillon')
    const table = container.querySelector('[data-dt-table]')
    const menus = within(table).getAllByLabelText("Plus d'actions sur la ligne")
    await user.click(menus[0])
    await user.click(await screen.findByText('Soumettre'))
    await waitFor(() => expect(gestionProjetApi.soumettreTimesheet).toHaveBeenCalledWith(1))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('« Approuver » sur une ligne soumise appelle l\'action serveur dédiée', async () => {
    const onChanged = vi.fn()
    const user = userEvent.setup()
    const { container } = render(<TimesheetsTab timesheets={timesheets} onChanged={onChanged} />)
    await screen.findByText('Soumise')
    const table = container.querySelector('[data-dt-table]')
    const menus = within(table).getAllByLabelText("Plus d'actions sur la ligne")
    await user.click(menus[1])
    await user.click(await screen.findByText('Approuver'))
    await waitFor(() => expect(gestionProjetApi.approuverTimesheet).toHaveBeenCalledWith(2))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })
})
