import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import CalendarView from './CalendarView'

/* VX144(d) — les leads sans date de relance ni de visite n'étaient signalés
   qu'en note de bas de page neutre (muted, invisible au balayage). On vérifie
   que `.cal-undated-label` porte l'accent --warning + une icône, jamais le
   texte muted d'avant. */

afterEach(() => { cleanup(); vi.clearAllMocks() })

const undatedLead = { id: 1, nom: 'Sans Date', stage: 'NEW' }

describe('CalendarView — VX144(d) accent --warning sur les leads sans date', () => {
  it('affiche le libellé sans-date avec la classe cal-undated-label + une icône', () => {
    render(<CalendarView leads={[undatedLead]} onOpenLead={vi.fn()} />)
    const label = screen.getByText(/sans date de/).closest('p')
    expect(label).toHaveClass('cal-undated-label')
    expect(label.querySelector('svg')).not.toBeNull()
  })

  it('ne rend rien pour la section sans-date quand tous les leads ont une date', () => {
    render(
      <CalendarView
        leads={[{ id: 2, nom: 'Avec Date', stage: 'NEW', relance_date: '2026-07-15' }]}
        onOpenLead={vi.fn()}
      />,
    )
    expect(screen.queryByText(/sans date de/)).toBeNull()
  })
})

describe('CalendarView — LB29 relance en retard soulignée (destructive)', () => {
  // Horloge FIGÉE mi-mois : la grille rend le MOIS COURANT — une date hors
  // mois ne rend AUCUN chip (l'échec CI/fold initial), et « hier » près du
  // 1er du mois glisserait au mois précédent (classe wall-clock #29).
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2026-07-15T10:00:00')) })
  afterEach(() => { vi.useRealTimers() })
  it('souligne (cal-chip-late) une relance dont la date est déjà passée', () => {
    render(
      <CalendarView
        leads={[{ id: 3, nom: 'Retard', stage: 'NEW', relance_date: '2026-07-10' }]}
        onOpenLead={vi.fn()}
      />,
    )
    const chip = screen.getByRole('button', { name: /Retard/ })
    expect(chip).toHaveClass('cal-chip-late')
  })

  it('ne souligne PAS une relance future', () => {
    render(
      <CalendarView
        leads={[{ id: 4, nom: 'Futur', stage: 'NEW', relance_date: '2026-07-25' }]}
        onOpenLead={vi.fn()}
      />,
    )
    const chip = screen.getByRole('button', { name: /Futur/ })
    expect(chip).not.toHaveClass('cal-chip-late')
  })

  it('ne double-signale jamais un lead perdu (pastille rouge seule, pas de soulignement)', () => {
    render(
      <CalendarView
        leads={[{
          id: 5, nom: 'PerduRetard', stage: 'COLD', perdu: true, relance_date: '2026-07-10',
        }]}
        onOpenLead={vi.fn()}
      />,
    )
    const chip = screen.getByRole('button', { name: /PerduRetard/ })
    expect(chip).toHaveClass('cal-chip-perdu')
    expect(chip).not.toHaveClass('cal-chip-late')
  })
})
