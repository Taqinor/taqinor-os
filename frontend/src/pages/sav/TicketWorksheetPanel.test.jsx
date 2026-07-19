import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR119 — Panneau de feuille de maintenance (worksheet) sur le ticket. */

const sav = vi.hoisted(() => ({
  getTicketWorksheet: vi.fn(),
  creerTicketWorksheet: vi.fn(() => Promise.resolve({ data: {} })),
  updateTicketWorksheet: vi.fn(),
  getWorksheetModeles: vi.fn(() => Promise.resolve({ data: [] })),
}))
vi.mock('../../api/savApi', () => ({ default: sav }))

import TicketWorksheetPanel from './TicketWorksheetPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const notFound = (detail) => Promise.reject({ response: { status: 404, data: { detail } } })

describe('TicketWorksheetPanel (WIR119)', () => {
  it('affiche une note d\'activation quand la fonctionnalité est désactivée', async () => {
    sav.getTicketWorksheet.mockReturnValue(notFound('Feuilles de maintenance non activées pour cette société.'))
    render(<TicketWorksheetPanel ticketId={1} />)
    expect(await screen.findByText(/ne sont pas activées/)).toBeInTheDocument()
  })

  it('propose la création depuis un modèle quand aucune feuille n\'existe', async () => {
    sav.getTicketWorksheet.mockReturnValue(notFound('Aucune feuille sur ce ticket.'))
    sav.getWorksheetModeles.mockResolvedValue({ data: [{ id: 3, nom: 'Visite PV', actif: true, champs: [] }] })
    const user = userEvent.setup()
    render(<TicketWorksheetPanel ticketId={1} />)
    await screen.findByText('Modèle')
    await user.selectOptions(screen.getByLabelText('Modèle'), '3')
    await user.click(screen.getByRole('button', { name: 'Créer la feuille' }))
    await waitFor(() => expect(sav.creerTicketWorksheet).toHaveBeenCalledWith(1, 3))
  })

  it('remplit une feuille existante et la marque complétée', async () => {
    sav.getTicketWorksheet.mockResolvedValue({
      data: {
        id: 8, ticket: 1, modele: 3, modele_nom: 'Visite PV',
        valeurs: {}, complete: false, champs_requis_manquants: ['pression'],
      },
    })
    sav.getWorksheetModeles.mockResolvedValue({
      data: [{ id: 3, nom: 'Visite PV', actif: true, champs: [
        { cle: 'pression', libelle: 'Pression', type: 'nombre', requis: true },
      ] }],
    })
    sav.updateTicketWorksheet.mockResolvedValue({
      data: { id: 8, modele: 3, modele_nom: 'Visite PV', valeurs: { pression: '5' }, complete: true, champs_requis_manquants: [] },
    })
    const user = userEvent.setup()
    render(<TicketWorksheetPanel ticketId={1} />)
    const input = await screen.findByLabelText(/Pression/)
    await user.type(input, '5')
    await user.click(screen.getByRole('button', { name: 'Marquer complétée' }))
    await waitFor(() => expect(sav.updateTicketWorksheet).toHaveBeenCalledWith(
      1, expect.objectContaining({ valeurs: { pression: '5' }, complete: true })))
    expect(await screen.findByText('Complétée')).toBeInTheDocument()
  })
})
