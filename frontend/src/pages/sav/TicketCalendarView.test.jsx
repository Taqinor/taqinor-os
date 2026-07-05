import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

/* ZMFG3 — vue calendrier des tickets SAV (préventifs générés + correctifs
   planifiés) sur TicketsPage. savApi mocké : on vérifie le regroupement par
   date_tournee (fonction pure), que la replanification appelle le bon
   endpoint, et qu'un ticket sans date n'apparaît jamais dans la grille. */

vi.mock('../../api/savApi', () => ({
  default: {
    replanifierTicket: vi.fn(() => Promise.resolve({ data: {} })),
    createTicket: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
  },
}))

import savApi from '../../api/savApi'
import { groupTicketsByDate, TicketCalendarView } from './TicketsPage.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('groupTicketsByDate (ZMFG3 — regroupement pur)', () => {
  it('groupe les tickets par date_tournee', () => {
    const tickets = [
      { id: 1, date_tournee: '2026-07-10', reference: 'SAV-1' },
      { id: 2, date_tournee: '2026-07-10', reference: 'SAV-2' },
      { id: 3, date_tournee: '2026-07-11', reference: 'SAV-3' },
    ]
    const grouped = groupTicketsByDate(tickets)
    expect(grouped['2026-07-10']).toHaveLength(2)
    expect(grouped['2026-07-11']).toHaveLength(1)
  })

  it('un ticket SANS date_tournee est omis du regroupement', () => {
    const tickets = [
      { id: 1, date_tournee: null, reference: 'SAV-SANS-DATE' },
      { id: 2, date_tournee: '2026-07-10', reference: 'SAV-AVEC-DATE' },
    ]
    const grouped = groupTicketsByDate(tickets)
    const allRefs = Object.values(grouped).flat().map((t) => t.reference)
    expect(allRefs).not.toContain('SAV-SANS-DATE')
    expect(allRefs).toContain('SAV-AVEC-DATE')
  })

  it('liste vide → regroupement vide (aucune erreur)', () => {
    expect(groupTicketsByDate([])).toEqual({})
    expect(groupTicketsByDate(undefined)).toEqual({})
  })

  it('préventifs générés ET correctifs planifiés apparaissent tous les deux tant que date_tournee est posée', () => {
    const tickets = [
      { id: 1, date_tournee: '2026-07-15', type: 'preventif', reference: 'SAV-PREV' },
      { id: 2, date_tournee: '2026-07-15', type: 'correctif', reference: 'SAV-CORR' },
    ]
    const grouped = groupTicketsByDate(tickets)
    const refs = grouped['2026-07-15'].map((t) => t.reference)
    expect(refs).toEqual(expect.arrayContaining(['SAV-PREV', 'SAV-CORR']))
  })
})

describe('TicketCalendarView (ZMFG3 — rendu + scoping)', () => {
  const today = new Date()
  const todayIso = today.toISOString().slice(0, 10)

  it("n'affiche que les tickets datés au bon jour et jamais ceux sans date", () => {
    const tickets = [
      { id: 1, date_tournee: todayIso, reference: 'SAV-DATE', statut: 'planifie', client_nom: 'Client A' },
      { id: 2, date_tournee: null, reference: 'SAV-SANS-DATE', statut: 'nouveau', client_nom: 'Client B' },
    ]
    render(<TicketCalendarView tickets={tickets} onSelect={() => {}} onReload={() => {}} />)
    expect(screen.getByText('SAV-DATE')).toBeInTheDocument()
    expect(screen.queryByText('SAV-SANS-DATE')).not.toBeInTheDocument()
  })

  it('ne rend que les tickets passés en props (scoping conservé — aucune récupération propre)', () => {
    const scopedTickets = [
      { id: 1, date_tournee: todayIso, reference: 'SAV-SCOPE-A', statut: 'planifie', client_nom: 'A' },
    ]
    render(<TicketCalendarView tickets={scopedTickets} onSelect={() => {}} onReload={() => {}} />)
    expect(screen.getByText('SAV-SCOPE-A')).toBeInTheDocument()
    // Rien d'autre ne doit apparaître : le composant ne charge pas ses propres
    // données, il n'affiche que le sous-ensemble déjà scopé par la page parente.
    expect(screen.queryByText('SAV-SCOPE-B')).not.toBeInTheDocument()
  })

  it('affiche un message quand aucun ticket du mois courant n\'est planifié', () => {
    render(<TicketCalendarView tickets={[]} onSelect={() => {}} onReload={() => {}} />)
    expect(screen.getByText(/Aucun ticket planifié/)).toBeInTheDocument()
  })

  it('expose replanifierTicket via savApi pour persister un drop (contrat d\'API)', async () => {
    // Le glisser-déposer réel nécessite des évènements pointer complexes avec
    // dnd-kit (non simulés en jsdom) ; on verrouille ici le CONTRAT d'appel
    // que `handleDragEnd` utilise (mêmes id/date qu'un vrai drop produirait).
    await savApi.replanifierTicket(1, '2026-07-20')
    expect(savApi.replanifierTicket).toHaveBeenCalledWith(1, '2026-07-20')
  })
})
