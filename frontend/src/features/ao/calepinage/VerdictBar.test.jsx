import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import VerdictBar from './VerdictBar'
import resultatReel from './resultatReel.fixture'

/* AOF93 — chaque valeur vient du résultat SERVEUR (`resultatReel.fixture.js`,
   capturé du moteur). Le badge « prouvé » n'apparaît que si le régime de
   preuve l'autorise (AOF44), et AUCUNE marge n'est recomposée ici. */

describe('VerdictBar — les champs RÉELS de /ao/calepinage/calculer/', () => {
  it('affiche les comptes serveur tels quels', () => {
    render(<VerdictBar resultat={resultatReel} />)
    expect(screen.getByText('16')).toBeInTheDocument()          // total_modules
    expect(screen.getByText('10 kWc')).toBeInTheDocument()      // kwc
    expect(screen.getByText('20 modules')).toBeInTheDocument()  // engagement_modules
  })

  it('publie le verdict d’engageabilité du serveur (`engageable`)', () => {
    const { container } = render(<VerdictBar resultat={resultatReel} />)
    expect(container.querySelector('[data-ao-verdict]').getAttribute('data-ao-verdict')).toBe('true')
    expect(screen.getByText('Compte engageable')).toBeInTheDocument()
    expect(container.querySelector('[data-motifs]')).toBeNull()
  })

  it('NON engageable : les motifs du moteur sont affichés verbatim', () => {
    const refuse = {
      ...resultatReel,
      engageable: false,
      motifs_non_engageable: ['A — obstacle deviné, non relevé'],
    }
    const { container } = render(<VerdictBar resultat={refuse} />)
    expect(container.querySelector('[data-ao-verdict]').getAttribute('data-ao-verdict')).toBe('false')
    expect(screen.getByText('A — obstacle deviné, non relevé')).toBeInTheDocument()
    expect(screen.getByText('Compte non engageable')).toBeInTheDocument()
  })

  it('badge de preuve : affiché sur une méthode EXACTE, absent sinon', () => {
    const { container, unmount } = render(<VerdictBar resultat={resultatReel} />)
    expect(container.querySelector('[data-preuve="prouve"]')).toBeInTheDocument()
    expect(screen.getByText('optimum prouvé (16 modules)')).toBeInTheDocument()
    unmount()

    const heuristique = {
      ...resultatReel,
      preuve: { ...resultatReel.preuve, methode: 'balayage_phase', methode_exacte: false },
    }
    const rendu = render(<VerdictBar resultat={heuristique} />)
    expect(rendu.container.querySelector('[data-preuve="prouve"]')).toBeNull()
    expect(screen.queryByText(/optimum prouvé/)).toBeNull()
    expect(screen.getByText('16')).toBeInTheDocument()          // …le reste est intact
  })

  it('AUCUNE marge n’est affichée : le serveur n’en publie pas', () => {
    const { container } = render(<VerdictBar resultat={resultatReel} />)
    expect(container.querySelector('[data-marge-signe]')).toBeNull()
    expect(screen.queryByText(/Marge/)).toBeNull()
  })

  it('sans `engagement_modules`, la case engagement disparaît (jamais un 0 inventé)', () => {
    render(<VerdictBar resultat={{ ...resultatReel, engagement_modules: null }} />)
    expect(screen.queryByText('Engagement au marché')).toBeNull()
    expect(screen.getByText('16')).toBeInTheDocument()
  })

  it('périmé : les grandeurs sont estompées et « recalcul… » est annoncé', () => {
    const { container } = render(<VerdictBar resultat={resultatReel} perime />)
    expect(screen.getByText('recalcul…')).toBeInTheDocument()
    expect(container.querySelector('[data-ao-verdict]').getAttribute('aria-busy')).toBe('true')
    const compteur = screen.getByText('16')
    expect(compteur.getAttribute('data-perime')).toBe('true')
    expect(compteur.className).toContain('opacity-40')
  })

  it('marque un résultat SERVI PAR LE CACHE', () => {
    const { container } = render(<VerdictBar resultat={{ ...resultatReel, depuis_cache: true }} />)
    expect(container.querySelector('[data-depuis-cache]')).toBeInTheDocument()
  })

  it("ne rend rien tant qu'aucun résultat n'est arrivé", () => {
    expect(render(<VerdictBar resultat={null} />).container.firstChild).toBeNull()
    expect(render(<VerdictBar resultat={{ repere: '05H' }} />).container.firstChild).toBeNull()
  })

  it('expose le compteur de modules sous le hook `data-ao-compte`', () => {
    const { container } = render(<VerdictBar resultat={resultatReel} />)
    expect(container.querySelector('[data-ao-compte="modules"]')).toBeInTheDocument()
  })
})
