import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import TachesCalendarView from './TachesCalendarView'

/* XPRJ11 — Vue calendrier mensuelle des tâches (positionnées par
   date_fin_prevue). Le composant ne fait AUCUN appel réseau lui-même : le
   parent (ProjetDetailPage) gère l'appel à `reprogrammer` + le rollback
   optimiste — on vérifie donc seulement le rendu ici (le drag lui-même est
   couvert par dnd-kit, testé ailleurs dans le kanban CRM). */

afterEach(() => { cleanup(); vi.clearAllMocks() })

function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

describe('TachesCalendarView', () => {
  it('rend le titre du mois courant et les en-têtes de semaine', () => {
    render(<TachesCalendarView taches={[]} onReprogrammer={vi.fn()} />)
    expect(screen.getByText('Lu')).toBeInTheDocument()
    expect(screen.getByText('Di')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Aujourd'hui/ })).toBeInTheDocument()
  })

  it('positionne une tâche sur sa date_fin_prevue', () => {
    const taches = [
      { id: 1, libelle: 'Mise en service', date_fin_prevue: todayISO() },
    ]
    render(<TachesCalendarView taches={taches} onReprogrammer={vi.fn()} />)
    expect(screen.getByText('Mise en service')).toBeInTheDocument()
  })

  it('ignore proprement les tâches sans date_fin_prevue', () => {
    const taches = [{ id: 2, libelle: 'Sans date', date_fin_prevue: null }]
    render(<TachesCalendarView taches={taches} onReprogrammer={vi.fn()} />)
    expect(screen.queryByText('Sans date')).not.toBeInTheDocument()
  })
})
