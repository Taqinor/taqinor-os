import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TiroirRives from './TiroirRives'

/* AOF97 — bornes AFFICHÉES, jamais imposées : aucun champ ne rejette ni
   n'arrondit une saisie légitime (même discipline que l'écran devis) ; les
   impacts chiffrés viennent du moteur. */

const DONNEES = {
  champs: [
    {
      code: 'rive_laterale_m',
      libelle: 'Rives latérales',
      unite: 'm',
      min: 0.3,
      max: 2,
      message_borne: 'Hors de la fourchette du CPS (0,30 m à 2,00 m) — à justifier au mémoire technique.',
      impacts: [
        { valeur: 0.5, texte_valeur: '0,50 m', impact_texte: '+8 modules', sens: 'gain' },
        { valeur: 1.5, texte_valeur: '1,50 m', impact_texte: '−12 modules', sens: 'perte' },
      ],
    },
    { code: 'rive_extremite_m', libelle: "Rives d'extrémité", unite: 'm', min: 0.3, max: 2 },
    { code: 'degagement_m', libelle: 'Dégagement standard', unite: 'm' },
    { code: 'degagement_inconnu_m', libelle: 'Dégagement — nature inconnue', unite: 'm' },
  ],
  variante_conservatrice: {
    libelle: 'Variante conservatrice historique (1,50 / 0,50 / 0,50)',
    valeurs: { rive_laterale_m: 1.5, rive_extremite_m: 0.5, degagement_m: 0.5 },
    comparaison_texte: 'À titre de comparaison : −12 modules par rapport au réglage courant.',
  },
}

const VALEURS = {
  rive_laterale_m: 0.5, rive_extremite_m: 0.5, degagement_m: 0.5, degagement_inconnu_m: 1,
}

const monter = (onChange = vi.fn(), valeurs = VALEURS) => {
  const utils = render(<TiroirRives donnees={DONNEES} valeurs={valeurs} onChange={onChange} />)
  return { ...utils, onChange }
}

describe('TiroirRives (AOF97)', () => {
  it('expose les 4 réglages du tiroir', () => {
    monter()
    expect(screen.getByLabelText('Rives latérales (m)')).toBeInTheDocument()
    expect(screen.getByLabelText("Rives d'extrémité (m)")).toBeInTheDocument()
    expect(screen.getByLabelText('Dégagement standard (m)')).toBeInTheDocument()
    expect(screen.getByLabelText('Dégagement — nature inconnue (m)')).toBeInTheDocument()
  })

  it('le formulaire est noValidate et chaque champ accepte step="any"', () => {
    monter()
    const champ = screen.getByLabelText('Rives latérales (m)')
    expect(champ).toHaveAttribute('step', 'any')
    expect(champ.closest('form')).toHaveAttribute('novalidate')
  })

  it("n'arrondit ni ne rejette une saisie légitime (0,473 reste 0,473)", () => {
    const { onChange } = monter()
    const champ = screen.getByLabelText('Rives latérales (m)')
    fireEvent.change(champ, { target: { value: '0.473' } })
    expect(champ).toHaveValue(0.473)
    expect(onChange).toHaveBeenLastCalledWith({ rive_laterale_m: 0.473 })
  })

  it('hors bornes : message FR affiché, mais la valeur saisie est CONSERVÉE', () => {
    const { container, onChange } = monter()
    const champ = screen.getByLabelText('Rives latérales (m)')
    fireEvent.change(champ, { target: { value: '3.5' } })
    expect(screen.getByText(/Hors de la fourchette du CPS/)).toBeInTheDocument()
    expect(champ).toHaveValue(3.5)                       // ni snapée…
    expect(onChange).toHaveBeenLastCalledWith({ rive_laterale_m: 3.5 }) // …ni rejetée.
    expect(container.querySelector('[data-borne="avertissement"]')).toBeInTheDocument()
  })

  it('dans les bornes : aucun avertissement', () => {
    const { container } = monter()
    fireEvent.change(screen.getByLabelText('Rives latérales (m)'), { target: { value: '1.5' } })
    expect(container.querySelector('[data-borne="avertissement"]')).toBeNull()
  })

  it("affiche l'impact chiffré du MOTEUR pour la valeur saisie", () => {
    monter()
    fireEvent.change(screen.getByLabelText('Rives latérales (m)'), { target: { value: '1.5' } })
    expect(screen.getByText('−12 modules')).toBeInTheDocument()
  })

  it("n'invente aucun impact pour une valeur que le moteur n'a pas chiffrée", () => {
    const { container } = monter()
    fireEvent.change(screen.getByLabelText('Rives latérales (m)'), { target: { value: '0.77' } })
    expect(container.querySelector('[data-impact="rive_laterale_m"]')).toBeNull()
    expect(container.querySelector('[data-impact-inconnu="rive_laterale_m"]')).toBeInTheDocument()
  })

  it('la variante conservatrice historique s\'applique en UN clic, avec son écart', async () => {
    const { onChange } = monter()
    expect(screen.getByText(/À titre de comparaison/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Variante conservatrice historique/ }))
    expect(onChange).toHaveBeenCalledWith({
      rive_laterale_m: 1.5, rive_extremite_m: 0.5, degagement_m: 0.5,
    })
  })

  it('expose le hook de tiroir `data-ao-tiroir`', () => {
    const { container } = monter()
    expect(container.querySelector('[data-ao-tiroir="rives"]')).toBeInTheDocument()
  })

  it('ne rend rien tant que le serveur ne décrit pas le tiroir', () => {
    const { container } = render(<TiroirRives donnees={null} />)
    expect(container.firstChild).toBeNull()
  })
})
