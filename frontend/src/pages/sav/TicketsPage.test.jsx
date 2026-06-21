import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  StatutPill,
  PrioriteBadge,
  TicketSlaBadge,
  KanbanColumn,
} from './TicketsPage.jsx'
import {
  TICKET_STATUSES,
  TICKET_STATUS_LABELS,
  TICKET_PRIORITE_LABELS,
} from '../../features/sav/ticketStatuses'

/* J144 — refonte SAV : les écrans tickets passent à StatusPill + DataTable, avec
   états vide / chargement et passe mobile. Ces tests verrouillent les briques de
   présentation (ton de statut, badge SLA, colonne Kanban) qui encodent cette
   refonte — la couleur n'est jamais le seul signal : le LIBELLÉ reste toujours. */

// Le point coloré du StatusPill encode le ton (bg-success/bg-warning/…) : on
// l'utilise pour vérifier le mapping statut → ton sans dépendre du thème.
const DOT_CLASS = {
  neutral: 'bg-muted-foreground', info: 'bg-info', success: 'bg-success',
  warning: 'bg-warning', danger: 'bg-destructive',
}

describe('StatutPill (J144 — statut ticket → ton + libellé FR)', () => {
  it('chaque statut canonique rend un libellé FR et un point coloré défini', () => {
    for (const k of TICKET_STATUSES) {
      const { container, unmount } = render(<StatutPill statut={k} />)
      // Libellé FR visible (jamais la clé brute).
      expect(screen.getByText(TICKET_STATUS_LABELS[k])).toBeInTheDocument()
      // Un point coloré d'un ton CONNU est rendu (la couleur n'est jamais seule).
      const hasKnownDot = Object.values(DOT_CLASS)
        .some((cls) => container.querySelector(`.${cls}`))
      expect(hasKnownDot).toBe(true)
      unmount()
    }
  })

  it('affiche le libellé FR du statut (jamais la clé brute)', () => {
    render(<StatutPill statut="en_cours" />)
    expect(screen.getByText(TICKET_STATUS_LABELS.en_cours)).toBeInTheDocument()
  })

  it('résolu → point coloré succès', () => {
    const { container } = render(<StatutPill statut="resolu" />)
    expect(container.querySelector(`.${DOT_CLASS.success}`)).toBeTruthy()
  })

  it('statut inconnu → ton neutre (jamais une erreur)', () => {
    const { container } = render(<StatutPill statut="zzz" />)
    expect(container.querySelector(`.${DOT_CLASS.neutral}`)).toBeTruthy()
  })
})

describe('PrioriteBadge (J144)', () => {
  it('affiche le libellé FR de la priorité', () => {
    render(<PrioriteBadge value="urgente" />)
    expect(screen.getByText(TICKET_PRIORITE_LABELS.urgente)).toBeInTheDocument()
  })

  it('chaque priorité connue rend son libellé FR', () => {
    for (const k of Object.keys(TICKET_PRIORITE_LABELS)) {
      const { unmount } = render(<PrioriteBadge value={k} />)
      expect(screen.getByText(TICKET_PRIORITE_LABELS[k])).toBeInTheDocument()
      unmount()
    }
  })
})

describe('TicketSlaBadge (J144 — âge SLA, calculé à la lecture)', () => {
  const openTicket = {
    statut: 'nouveau',
    priorite: 'normale',
    annule: false,
    date_ouverture: '2000-01-01', // très ancien → forcément ouvert depuis N j
  }

  it('affiche « ouvert depuis X j » pour un ticket ouvert', () => {
    render(<TicketSlaBadge ticket={openTicket} />)
    expect(screen.getByText(/ouvert depuis/i)).toBeInTheDocument()
  })

  it('ne rend rien pour un ticket clôturé', () => {
    const { container } = render(
      <TicketSlaBadge ticket={{ ...openTicket, statut: 'cloture' }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('ne rend rien pour un ticket annulé', () => {
    const { container } = render(
      <TicketSlaBadge ticket={{ ...openTicket, annule: true }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('ne rend rien sans date exploitable', () => {
    const { container } = render(
      <TicketSlaBadge ticket={{ statut: 'nouveau', priorite: 'normale', annule: false }} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})

describe('KanbanColumn (J144 — vue Kanban par statut)', () => {
  const tickets = [
    { id: 1, reference: 'SAV-001', client_nom: 'ACME', priorite: 'haute', statut: 'nouveau' },
    { id: 2, reference: 'SAV-002', client_nom: 'Globex', priorite: 'basse', statut: 'nouveau' },
  ]

  it('rend le libellé FR du statut en en-tête et le compte des cartes', () => {
    render(<KanbanColumn statut="nouveau" tickets={tickets} onSelect={() => {}} />)
    expect(screen.getByText(TICKET_STATUS_LABELS.nouveau)).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('SAV-001')).toBeInTheDocument()
    expect(screen.getByText('SAV-002')).toBeInTheDocument()
  })

  it('affiche un « — » quand la colonne est vide (état vide)', () => {
    render(<KanbanColumn statut="resolu" tickets={[]} onSelect={() => {}} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('appelle onSelect avec le ticket cliqué', async () => {
    const onSelect = vi.fn()
    render(<KanbanColumn statut="nouveau" tickets={tickets} onSelect={onSelect} />)
    await userEvent.click(screen.getByText('SAV-001'))
    expect(onSelect).toHaveBeenCalledWith(tickets[0])
  })
})
