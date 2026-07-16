import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ChatterTimeline from './ChatterTimeline'

/* VX23 — ChatterTimeline : regroupement par jour, avatars, distinction note
   manuelle / log auto de champ, pièces jointes injectées dans le fil. */

afterEach(() => { cleanup() })

const NOW = new Date()
const isoAt = (hoursAgo) => new Date(NOW.getTime() - hoursAgo * 3600000).toISOString()
// Ancré sur le jour calendaire LOCAL à midi (12 h de marge de part et d'autre
// de minuit) : le regroupement Aujourd'hui/Hier de dayLabel() compare des jours
// locaux, donc « il y a 1 h » basculait sur la veille quand la suite tournait
// juste après minuit (run CI 00:3x UTC → « Aujourd'hui » absent, faux échec).
const localNoon = (daysAgo) =>
  new Date(NOW.getFullYear(), NOW.getMonth(), NOW.getDate() - daysAgo, 12, 0, 0).toISOString()

describe('ChatterTimeline (VX23)', () => {
  it("affiche le message vide quand il n'y a ni activité ni pièce jointe", () => {
    render(<ChatterTimeline entries={[]} />)
    expect(screen.getByText('Aucune activité pour le moment.')).toBeInTheDocument()
  })

  it('regroupe les entrées par jour avec les labels Aujourd\'hui / Hier', () => {
    render(
      <ChatterTimeline
        entries={[
          { id: 1, kind: 'note', body: 'Note du jour', user_nom: 'Sami', created_at: localNoon(0) },
          { id: 2, kind: 'note', body: 'Note d’hier', user_nom: 'Sami', created_at: localNoon(1) },
        ]}
      />,
    )
    expect(screen.getByText("Aujourd'hui")).toBeInTheDocument()
    expect(screen.getByText('Hier')).toBeInTheDocument()
  })

  it('distingue visuellement une note manuelle (fond plein) d\'un log auto de champ (discret)', () => {
    render(
      <ChatterTimeline
        entries={[
          { id: 1, kind: 'note', body: 'Appel effectué', user_nom: 'Sami', created_at: isoAt(1) },
          {
            id: 2, kind: 'modification', field_label: 'Étape', old_value: 'Nouveau',
            new_value: 'Contacté', user_nom: 'Sami', created_at: isoAt(2),
          },
        ]}
      />,
    )
    const note = document.querySelector('.chatter-item-note')
    const autolog = document.querySelector('.chatter-item-autolog')
    expect(note).toBeTruthy()
    expect(autolog).toBeTruthy()
  })

  it('injecte les pièces jointes récentes dans le fil (pas un onglet séparé)', () => {
    render(
      <ChatterTimeline
        entries={[{ id: 1, kind: 'note', body: 'Note', user_nom: 'Sami', created_at: isoAt(1) }]}
        attachments={[
          { id: 99, filename: 'facture.pdf', url: '/x', uploaded_by_nom: 'Sami', created_at: isoAt(0.5) },
        ]}
      />,
    )
    expect(screen.getByText('facture.pdf')).toBeInTheDocument()
  })

  it('rend un Avatar par entrée', () => {
    render(
      <ChatterTimeline
        entries={[{ id: 1, kind: 'note', body: 'Note', user_nom: 'Sami Test', created_at: isoAt(1) }]}
      />,
    )
    // Avatar sans photo → initiales du nom.
    expect(screen.getByTitle('Sami Test')).toBeInTheDocument()
  })
})
