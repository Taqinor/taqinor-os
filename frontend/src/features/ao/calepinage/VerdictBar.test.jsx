import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import VerdictBar from './VerdictBar'

/* AOF93 — chaque valeur vient du résultat SERVEUR ; le verdict n'est jamais
   rédigé à la main et le badge « prouvé » n'apparaît que si le régime de
   preuve l'autorise (AOF44). */

const base = {
  modules: { valeur: 314, texte: '314 modules' },
  puissance: { valeur: 196.25, texte: '196,25 kWc' },
  engagement: { valeur: 190, texte: '190,00 kWc' },
  verdict: { code: 'confirme', libelle: 'CONFIRMÉ', motif: "Capacité au-dessus de l'engagement." },
  preuve: { prouve: true, badge: 'optimum prouvé — programmation dynamique au pas de 1 cm' },
  sceau: { dessine_compte: true, libelle: 'dessiné = compté' },
}

const margePositive = { ...base, marge: { valeur: 6.25, texte: '+6,25 kWc', signe: 'positif' } }
const margeNulle = { ...base, marge: { valeur: 0, texte: '0,00 kWc', signe: 'nul' } }
const margeNegative = {
  ...base,
  marge: { valeur: -4.5, texte: '−4,50 kWc', signe: 'negatif' },
  verdict: { code: 'tendu', libelle: 'TENDU', motif: "Capacité sous l'engagement." },
  ligne_ajustement: {
    requise: true,
    mention: "Capacité sous l'engagement : une ligne d'ajustement sera portée au bordereau.",
  },
}

const signe = (container) => container.querySelector('[data-marge-signe]')?.getAttribute('data-marge-signe')

describe('VerdictBar (AOF93)', () => {
  it('affiche les textes SERVEUR tels quels (aucun formatage front)', () => {
    render(<VerdictBar resultat={margePositive} />)
    expect(screen.getByText('314 modules')).toBeInTheDocument()
    expect(screen.getByText('196,25 kWc')).toBeInTheDocument()
    expect(screen.getByText('190,00 kWc')).toBeInTheDocument()
    expect(screen.getByText('+6,25 kWc')).toBeInTheDocument()
  })

  it('marge POSITIVE : verdict CONFIRMÉ, aucune mention de ligne d\'ajustement', () => {
    const { container } = render(<VerdictBar resultat={margePositive} />)
    expect(container.querySelector('[data-ao-verdict]').getAttribute('data-ao-verdict')).toBe('confirme')
    expect(screen.getByText('CONFIRMÉ')).toBeInTheDocument()
    expect(signe(container)).toBe('positif')
    expect(container.querySelector('[data-ligne-ajustement]')).toBeNull()
  })

  it('marge NULLE : la barre reste affichée, marge signée « nul »', () => {
    const { container } = render(<VerdictBar resultat={margeNulle} />)
    expect(screen.getByText('0,00 kWc')).toBeInTheDocument()
    expect(signe(container)).toBe('nul')
    expect(container.querySelector('[data-ligne-ajustement]')).toBeNull()
  })

  it('marge NÉGATIVE : verdict TENDU + mention automatique de ligne d\'ajustement', () => {
    const { container } = render(<VerdictBar resultat={margeNegative} />)
    expect(container.querySelector('[data-ao-verdict]').getAttribute('data-ao-verdict')).toBe('tendu')
    expect(screen.getByText('TENDU')).toBeInTheDocument()
    expect(signe(container)).toBe('negatif')
    expect(
      screen.getByText("Capacité sous l'engagement : une ligne d'ajustement sera portée au bordereau."),
    ).toBeInTheDocument()
  })

  it('méthode HEURISTIQUE : le badge « optimum prouvé » est ABSENT', () => {
    const heuristique = { ...margePositive, preuve: { prouve: false, badge: 'optimum prouvé' } }
    const { container } = render(<VerdictBar resultat={heuristique} />)
    expect(container.querySelector('[data-preuve="prouve"]')).toBeNull()
    expect(screen.queryByText(/optimum prouvé/)).toBeNull()
    // …mais le reste de la barre est intact.
    expect(screen.getByText('314 modules')).toBeInTheDocument()
  })

  it('affiche le badge « prouvé » et le sceau « dessiné = compté » du serveur', () => {
    const { container } = render(<VerdictBar resultat={margePositive} />)
    expect(container.querySelector('[data-preuve="prouve"]')).toBeInTheDocument()
    expect(screen.getByText(/optimum prouvé — programmation dynamique au pas de 1 cm/)).toBeInTheDocument()
    expect(screen.getByText(/dessiné = compté/)).toBeInTheDocument()
  })

  it('périmé : les grandeurs sont estompées et « recalcul… » est annoncé', () => {
    const { container } = render(<VerdictBar resultat={margePositive} perime />)
    expect(screen.getByText('recalcul…')).toBeInTheDocument()
    expect(container.querySelector('[data-ao-verdict]').getAttribute('aria-busy')).toBe('true')
    const modules = screen.getByText('314 modules')
    expect(modules.getAttribute('data-perime')).toBe('true')
    expect(modules.className).toContain('opacity-40')
  })

  it("ne rend rien tant que le serveur n'a pas renvoyé de verdict", () => {
    const { container } = render(<VerdictBar resultat={{ modules: { valeur: 1, texte: '1' } }} />)
    expect(container.firstChild).toBeNull()
  })

  it('expose le compteur de modules sous le hook `data-ao-compte`', () => {
    const { container } = render(<VerdictBar resultat={margePositive} />)
    expect(container.querySelector('[data-ao-compte="modules"]')).toBeInTheDocument()
  })
})
