import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* WR11 / FG82 — checklist de maintenance du ticket : init depuis un template,
   items cochables, note par item. savApi mocké. */

const ITEMS = [
  { id: 1, cle: 'panneaux', libelle: 'Nettoyage des panneaux', ordre: 1,
    coche: false, note: '', coche_par_nom: null, date_coche: null },
  { id: 2, cle: 'serrage', libelle: 'Serrage des connexions', ordre: 2,
    coche: true, note: 'RAS', coche_par_nom: 'tech1',
    date_coche: '2026-06-28T09:00:00Z' },
]

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({
      data: [{ id: 5, nom: 'Visite annuelle', actif: true, items: [] }],
    })),
    initTicketChecklist: vi.fn(() => Promise.resolve({ data: ITEMS })),
    patchTicketChecklistItem: vi.fn(() => Promise.resolve({
      data: { ...ITEMS[0], coche: true, coche_par_nom: 'moi' },
    })),
  },
}))

import savApi from '../../api/savApi'
import TicketChecklistPanel from './TicketChecklistPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TicketChecklistPanel (WR11 — FG82)', () => {
  it('propose l\'initialisation depuis un modèle quand la checklist est vide', async () => {
    render(<TicketChecklistPanel ticketId={9} />)
    await waitFor(() =>
      expect(screen.getByText(/Aucune checklist sur ce ticket/)).toBeInTheDocument())
    expect(savApi.getTicketChecklist).toHaveBeenCalledWith(9)
    expect(savApi.getChecklistTemplates).toHaveBeenCalled()
    // Le bouton est désactivé tant qu'aucun modèle n'est choisi.
    expect(screen.getByRole('button', { name: /Initialiser/ })).toBeDisabled()
  })

  it('rend les items et coche via PATCH {cle, coche}', async () => {
    savApi.getTicketChecklist.mockResolvedValueOnce({ data: ITEMS })
    render(<TicketChecklistPanel ticketId={9} />)
    await waitFor(() =>
      expect(screen.getByText('Nettoyage des panneaux')).toBeInTheDocument())
    expect(screen.getByText('Serrage des connexions')).toBeInTheDocument()
    expect(screen.getByText('1/2 points coché.')).toBeInTheDocument()

    const boxes = screen.getAllByRole('checkbox')
    fireEvent.click(boxes[0])
    await waitFor(() => expect(savApi.patchTicketChecklistItem)
      .toHaveBeenCalledWith(9, { cle: 'panneaux', coche: true }))
  })

  it('enregistre une note au blur via PATCH {cle, note}', async () => {
    savApi.getTicketChecklist.mockResolvedValueOnce({ data: ITEMS })
    savApi.patchTicketChecklistItem.mockResolvedValueOnce({
      data: { ...ITEMS[0], note: 'à revoir' },
    })
    render(<TicketChecklistPanel ticketId={9} />)
    const note = await screen.findByLabelText('Note — Nettoyage des panneaux')
    fireEvent.change(note, { target: { value: 'à revoir' } })
    fireEvent.blur(note)
    await waitFor(() => expect(savApi.patchTicketChecklistItem)
      .toHaveBeenCalledWith(9, { cle: 'panneaux', note: 'à revoir' }))
  })
})
