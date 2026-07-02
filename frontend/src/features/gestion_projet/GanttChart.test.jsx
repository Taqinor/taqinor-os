import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import GanttChart from './GanttChart.jsx'
import { StatutProjet } from './constants.jsx'

/* UX39 — Smoke test du rendu Gantt + fabrique de pastille de statut. */

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('GanttChart', () => {
  it('rend une ligne par tâche datée avec les bornes d’échelle', () => {
    withProviders(
      <GanttChart
        taches={[
          { id: 1, libelle: 'Étude', code_wbs: '1', statut: 'termine', date_debut_prevue: '2026-01-01', date_fin_prevue: '2026-01-05', avancement_pct: 100 },
          { id: 2, libelle: 'Pose', code_wbs: '2', statut: 'en_cours', date_debut_prevue: '2026-01-06', date_fin_prevue: '2026-01-12', avancement_pct: 40 },
        ]}
        jalons={[{ id: 9, libelle: 'MES', date_prevue: '2026-01-12', statut: 'a_venir' }]}
        dependances={[{ id: 3, predecesseur: 1, successeur: 2, type_dependance: 'fs', lag: 0 }]}
      />,
    )
    expect(screen.getByText('Étude')).toBeInTheDocument()
    expect(screen.getByText('Pose')).toBeInTheDocument()
    expect(screen.getByLabelText('Diagramme de Gantt')).toBeInTheDocument()
    // Légende de dépendance visible.
    expect(screen.getByText(/#1 → #2/)).toBeInTheDocument()
  })

  it('affiche un état vide quand aucune tâche n’est datée', () => {
    withProviders(<GanttChart taches={[{ id: 1, libelle: 'X' }]} />)
    expect(screen.getByText('Aucune tâche datée')).toBeInTheDocument()
  })
})

describe('StatutProjet', () => {
  it('mappe une valeur de statut vers son libellé français', () => {
    withProviders(<StatutProjet status="en_cours" />)
    expect(screen.getByText('En cours')).toBeInTheDocument()
  })
})
