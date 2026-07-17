import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ChatterTimeline, { parseMarketingTouch } from './ChatterTimeline'

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

// ── NTMKT11 — touches marketing distinguées dans le chatter ──
describe('parseMarketingTouch (NTMKT11, logique pure)', () => {
  it('reconnaît une touche de campagne (envoyée/ouverte/cliquée)', () => {
    expect(parseMarketingTouch('Campagne « Réveil été » envoyée'))
      .toEqual({ type: 'campagne', nom: 'Réveil été' })
    expect(parseMarketingTouch('Campagne « Promo Ramadan » ouverte'))
      .toEqual({ type: 'campagne', nom: 'Promo Ramadan' })
  })

  it('reconnaît une touche de séquence', () => {
    expect(parseMarketingTouch('Séquence « Onboarding partenaire » — relance commerciale créée'))
      .toEqual({ type: 'sequence', nom: 'Onboarding partenaire' })
  })

  it("une note manuelle ordinaire n'est pas reconnue comme touche marketing", () => {
    expect(parseMarketingTouch('Appel client — intéressé')).toBeNull()
    expect(parseMarketingTouch('')).toBeNull()
    expect(parseMarketingTouch(null)).toBeNull()
    expect(parseMarketingTouch(undefined)).toBeNull()
  })
})

describe('ChatterTimeline — touches marketing (NTMKT11)', () => {
  it('une touche marketing porte la classe dédiée + icône Megaphone', () => {
    render(
      <ChatterTimeline
        entries={[{ id: 1, kind: 'note', body: 'Campagne « Réveil » envoyée', user_nom: null, created_at: isoAt(1) }]}
      />,
    )
    expect(document.querySelector('.chatter-item-marketing')).toBeTruthy()
    expect(document.querySelector('.chatter-marketing-icon')).toBeTruthy()
  })

  it('affiche un lien cliquable quand resolveMarketingLink résout une URL', () => {
    render(
      <ChatterTimeline
        entries={[{ id: 1, kind: 'note', body: 'Campagne « Réveil » envoyée', user_nom: null, created_at: isoAt(1) }]}
        resolveMarketingLink={(type, nom) => (type === 'campagne' && nom === 'Réveil' ? '/marketing/campagnes/7' : null)}
      />,
    )
    const lien = screen.getByText('Voir la campagne')
    expect(lien.closest('a')).toHaveAttribute('href', '/marketing/campagnes/7')
  })

  it('aucun lien affiché sans resolveMarketingLink (comportement par défaut inchangé)', () => {
    render(
      <ChatterTimeline
        entries={[{ id: 1, kind: 'note', body: 'Campagne « Réveil » envoyée', user_nom: null, created_at: isoAt(1) }]}
      />,
    )
    expect(screen.queryByText('Voir la campagne')).toBeNull()
    // La note reste malgré tout visible et taguée.
    expect(document.querySelector('.chatter-item-marketing')).toBeTruthy()
  })

  it('une note manuelle ordinaire ne porte pas la classe marketing', () => {
    render(
      <ChatterTimeline
        entries={[{ id: 1, kind: 'note', body: 'Appel effectué', user_nom: 'Sami', created_at: isoAt(1) }]}
      />,
    )
    expect(document.querySelector('.chatter-item-marketing')).toBeFalsy()
  })
})
