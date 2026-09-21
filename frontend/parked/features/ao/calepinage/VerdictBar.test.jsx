import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

/* ============================================================================
   PV32 — état du mode « rangées imposées par l'utilisateur ».
   ----------------------------------------------------------------------------
   `preuve.methode === 'impose_utilisateur'` (vocabulaire VERROUILLÉ d'AOF44)
   et l'écart LU tel quel sur `plans[0].ecart_a_l_optimum` — jamais reconstitué
   par soustraction de `total_optimal`/`total_retenu` (voir l'en-tête du
   fichier). Le bouton « Enregistrer comme variante » est INJECTÉ : absent
   sans `onEnregistrerVariante`, comme `onDefinirRetenue` dans
   `VariantesCompare.jsx`.
   ========================================================================== */
describe('VerdictBar (PV32) — plan imposé, écart à l’optimum, enregistrement', () => {
  const impose = {
    ...resultatReel,
    plans: [{ ...resultatReel.plans[0], ecart_a_l_optimum: 6 }],
    preuve: {
      ...resultatReel.preuve,
      methode: 'impose_utilisateur',
      methode_exacte: false,
      optimal: false,
      total_optimal: 22,
      total_retenu: 16,
    },
  }

  it('un plan IMPOSÉ se présente comme non optimal, jamais comme un optimum prouvé', () => {
    render(<VerdictBar resultat={impose} />)
    expect(screen.getByText('Plan imposé — non optimal')).toBeInTheDocument()
    expect(screen.queryByText(/optimum prouvé/)).toBeNull()
  })

  it('l’écart affiché est celui du MOTEUR (`plans[0].ecart_a_l_optimum`), verbatim', () => {
    const { container } = render(<VerdictBar resultat={impose} />)
    expect(screen.getByText('-6 modules vs optimum')).toBeInTheDocument()
    expect(container.querySelector('[data-ao-ecart-optimum]')).toBeInTheDocument()
  })

  it('hors mode imposé, ni le badge « plan imposé » ni l’écart n’apparaissent', () => {
    render(<VerdictBar resultat={resultatReel} />)
    expect(screen.queryByText('Plan imposé — non optimal')).toBeNull()
    expect(screen.queryByText(/vs optimum/)).toBeNull()
  })

  it('sans `onEnregistrerVariante`, aucun bouton d’enregistrement (même en mode imposé)', () => {
    render(<VerdictBar resultat={impose} />)
    expect(screen.queryByRole('button', { name: /Enregistrer comme variante/ })).toBeNull()
  })

  it('« Enregistrer comme variante » : présent quand injecté, appelle le callback au clic', async () => {
    const onEnregistrerVariante = vi.fn()
    render(<VerdictBar resultat={impose} onEnregistrerVariante={onEnregistrerVariante} />)
    const bouton = screen.getByRole('button', { name: /Enregistrer comme variante/ })
    await userEvent.click(bouton)
    expect(onEnregistrerVariante).toHaveBeenCalledTimes(1)
  })
})
