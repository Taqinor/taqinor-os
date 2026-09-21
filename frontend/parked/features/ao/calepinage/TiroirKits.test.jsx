import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TiroirKits from './TiroirKits'

/* AOF95 — aucun chiffre de comparaison n'est saisi à la main : la
   contre-épreuve, la composition et la recommandation viennent du moteur. */

const DONNEES = {
  kits: [
    { code: 'portrait', libelle: 'Portrait' },
    { code: 'paysage', libelle: 'Paysage' },
    { code: 'mixte', libelle: 'Mixte', recommande: true },
  ],
  granularites: [
    { code: 'site', libelle: 'Site' },
    { code: 'zone', libelle: 'Zone' },
    { code: 'rangee', libelle: 'Rangée' },
    { code: 'segment', libelle: 'Segment' },
  ],
  recommandation: { code: 'mixte', libelle: 'mixte' },
  composition: { texte: '13 rangées : 4 portrait + 9 paysage', total_texte: '178 modules' },
  contre_epreuve: [{
    id: 'S-B',
    segment: 'Segment B',
    options: [
      { code: 'paysage', libelle: 'en paysage', texte: '34' },
      { code: 'portrait', libelle: 'en portrait', texte: '24' },
    ],
    motif: 'la cage de 5,93 interdit toute rangée large',
  }],
}

const VALEURS = { kit: 'mixte', granularite_kit: 'zone' }

describe('TiroirKits (AOF95)', () => {
  it('affiche la composition retenue et son total tels que renvoyés', () => {
    render(<TiroirKits donnees={DONNEES} valeurs={VALEURS} />)
    expect(screen.getByText('13 rangées : 4 portrait + 9 paysage')).toBeInTheDocument()
    expect(screen.getByText('178 modules')).toBeInTheDocument()
  })

  it('affiche la CONTRE-ÉPREUVE du moteur, chiffres et motif compris', () => {
    render(<TiroirKits donnees={DONNEES} valeurs={VALEURS} />)
    expect(screen.getByText('Segment B')).toBeInTheDocument()
    expect(screen.getByText('en paysage : 34 · en portrait : 24')).toBeInTheDocument()
    expect(screen.getByText('la cage de 5,93 interdit toute rangée large')).toBeInTheDocument()
  })

  it("n'invente aucune contre-épreuve quand le moteur n'en renvoie pas", () => {
    const { container } = render(<TiroirKits donnees={{ ...DONNEES, contre_epreuve: [] }} valeurs={VALEURS} />)
    expect(container.querySelector('[data-contre-epreuve]')).toBeNull()
  })

  it('porte le chip « recommandé : mixte » du serveur', () => {
    const { container } = render(<TiroirKits donnees={DONNEES} valeurs={VALEURS} />)
    expect(container.querySelector('[data-recommande="mixte"]')).toBeInTheDocument()
    expect(screen.getByText(/recommandé : mixte/)).toBeInTheDocument()
  })

  it('changer de kit remonte le paramètre (le recalcul appartient au serveur)', async () => {
    const onChange = vi.fn()
    render(<TiroirKits donnees={DONNEES} valeurs={VALEURS} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Paysage' }))
    expect(onChange).toHaveBeenCalledWith({ kit: 'paysage' })
  })

  it('changer de granularité remonte le paramètre', async () => {
    const onChange = vi.fn()
    render(<TiroirKits donnees={DONNEES} valeurs={VALEURS} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Segment' }))
    expect(onChange).toHaveBeenCalledWith({ granularite_kit: 'segment' })
  })

  it("l'argument d'approvisionnement n'apparaît QUE s'il est confirmé (AOF119)", () => {
    const argument = 'Les 2 kits sont ceux des bâtiments déjà approvisionnés — aucun approvisionnement nouveau.'
    const { container: nonConfirme } = render(
      <TiroirKits donnees={{ ...DONNEES, approvisionnement: { confirme: false, argument } }} valeurs={VALEURS} />,
    )
    expect(nonConfirme.querySelector('[data-approvisionnement]')).toBeNull()
    expect(screen.queryByText(argument)).toBeNull()

    const { container: confirme } = render(
      <TiroirKits donnees={{ ...DONNEES, approvisionnement: { confirme: true, argument } }} valeurs={VALEURS} />,
    )
    expect(confirme.querySelector('[data-approvisionnement="confirme"]')).toBeInTheDocument()
    expect(screen.getByText(argument)).toBeInTheDocument()
  })

  it('estompe la composition pendant un recalcul (jamais donnée pour courante)', () => {
    const { container } = render(<TiroirKits donnees={DONNEES} valeurs={VALEURS} perime />)
    expect(container.querySelector('[data-composition]').getAttribute('data-perime')).toBe('true')
  })

  it('expose le hook de tiroir `data-ao-tiroir`', () => {
    const { container } = render(<TiroirKits donnees={DONNEES} valeurs={VALEURS} />)
    expect(container.querySelector('[data-ao-tiroir="kits"]')).toBeInTheDocument()
  })

  it('ne rend rien tant que le serveur ne décrit pas le tiroir', () => {
    const { container } = render(<TiroirKits donnees={null} />)
    expect(container.firstChild).toBeNull()
  })
})
