import { describe, it, expect, vi, afterEach } from 'vitest'
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
