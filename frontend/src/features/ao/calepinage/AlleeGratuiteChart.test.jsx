import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AlleeGratuiteChart from './AlleeGratuiteChart'
import TiroirAllees from './TiroirAllees'

/* AOF96 — le plateau GRATUIT du cas réel (bâtiment C : compte identique de
   0,60 m à 1,94 m) doit être une affordance, pas une découverte. */

const point = (largeur, compte, texteLargeur) => ({
  largeur_m: largeur,
  compte,
  texte_largeur: texteLargeur,
  texte_compte: String(compte),
})

const GRAPHE = {
  points: [
    point(0.6, 314, '0,60 m'),
    point(1.0, 314, '1,00 m'),
    point(1.5, 314, '1,50 m'),
    point(1.94, 314, '1,94 m'),
    point(2.2, 290, '2,20 m'),
    point(2.6, 266, '2,60 m'),
  ],
  plateau: {
    debut_m: 0.6,
    fin_m: 1.94,
    texte_debut: '0,60 m',
    texte_fin: '1,94 m',
    resume: 'Compte identique de 0,60 m à 1,94 m — 1,90 m de maintenance offerts.',
    largeur_offerte_m: 1.9,
    libelle_bouton: 'Offrir 1,90 m de maintenance (sans perte)',
  },
}

const cxDuPoint = (container, texte) =>
  container.querySelector(`circle[data-largeur="${texte}"]`)?.getAttribute('cx')

describe('AlleeGratuiteChart (AOF96)', () => {
  it('surligne le plateau exactement entre les deux bornes du moteur', () => {
    const { container } = render(<AlleeGratuiteChart graphe={GRAPHE} />)
    const bande = container.querySelector('rect[data-plateau="gratuit"]')
    expect(bande).toBeInTheDocument()
    const debut = Number(bande.getAttribute('x'))
    const fin = debut + Number(bande.getAttribute('width'))
    expect(debut).toBeCloseTo(Number(cxDuPoint(container, '0,60 m')), 6)
    expect(fin).toBeCloseTo(Number(cxDuPoint(container, '1,94 m')), 6)
  })

  it('affiche les bornes et le résumé du plateau tels que renvoyés', () => {
    render(<AlleeGratuiteChart graphe={GRAPHE} />)
    expect(screen.getByText('0,60 m')).toBeInTheDocument()
    expect(screen.getByText('1,94 m')).toBeInTheDocument()
    expect(screen.getByText(/1,90 m de maintenance offerts/)).toBeInTheDocument()
  })

  it('trace un point par largeur renvoyée, sans en inventer', () => {
    const { container } = render(<AlleeGratuiteChart graphe={GRAPHE} />)
    expect(container.querySelectorAll('circle[data-item="point"]')).toHaveLength(6)
  })

  it('un clic applique la plus grande largeur GRATUITE (valeur du moteur)', async () => {
    const onAppliquer = vi.fn()
    render(<AlleeGratuiteChart graphe={GRAPHE} onAppliquer={onAppliquer} />)
    await userEvent.click(screen.getByRole('button', { name: 'Offrir 1,90 m de maintenance (sans perte)' }))
    expect(onAppliquer).toHaveBeenCalledWith(1.9)
  })

  it('sans plateau renvoyé : aucun surlignage, aucun bouton (rien n\'est déduit)', () => {
    const { container } = render(<AlleeGratuiteChart graphe={{ points: GRAPHE.points }} />)
    expect(container.querySelector('[data-plateau]')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('reste lisible en clair ET en sombre : aucune couleur en dur', () => {
    const { container } = render(<AlleeGratuiteChart graphe={GRAPHE} />)
    const html = container.innerHTML
    expect(html).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
    expect(html).not.toMatch(/rgba?\(/)
    // …les teintes viennent des jetons de thème (paires clair/sombre).
    expect(container.querySelector('rect[data-plateau]').getAttribute('class')).toContain('fill-success')
    expect(container.querySelector('polyline').getAttribute('class')).toContain('stroke-primary')
  })

  it('ne rend rien sans point renvoyé par le moteur', () => {
    const { container } = render(<AlleeGratuiteChart graphe={{ points: [] }} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('TiroirAllees (AOF96)', () => {
  const DONNEES = {
    presets: [
      { code: 'minimum', libelle: '0,60 minimum', largeur_m: 0.6 },
      { code: 'maintenance', libelle: 'Allée de maintenance', largeur_m: 1.9 },
    ],
    graphe: GRAPHE,
  }

  it('propose les préréglages du serveur et remonte la largeur choisie', async () => {
    const onChange = vi.fn()
    render(<TiroirAllees donnees={DONNEES} valeurs={{ allee_m: 0.6 }} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Allée de maintenance' }))
    expect(onChange).toHaveBeenCalledWith({ allee_m: 1.9 })
  })

  it('accepte une largeur libre sans jamais arrondir ni rejeter la saisie', () => {
    const onChange = vi.fn()
    render(<TiroirAllees donnees={DONNEES} valeurs={{ allee_m: 0.6 }} onChange={onChange} />)
    const champ = screen.getByLabelText(/Largeur d'allée/)
    expect(champ).toHaveAttribute('step', 'any')
    expect(champ.closest('form')).toHaveAttribute('novalidate')
    fireEvent.change(champ, { target: { value: '1.937' } })
    expect(onChange).toHaveBeenLastCalledWith({ allee_m: 1.937 })
    expect(champ).toHaveValue(1.937)
  })

  it('le bouton du plateau applique la largeur gratuite comme paramètre', async () => {
    const onChange = vi.fn()
    render(<TiroirAllees donnees={DONNEES} valeurs={{ allee_m: 0.6 }} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Offrir 1,90 m de maintenance (sans perte)' }))
    expect(onChange).toHaveBeenCalledWith({ allee_m: 1.9 })
  })

  it('expose le hook de tiroir `data-ao-tiroir`', () => {
    const { container } = render(<TiroirAllees donnees={DONNEES} valeurs={{ allee_m: 0.6 }} />)
    expect(container.querySelector('[data-ao-tiroir="allees"]')).toBeInTheDocument()
  })
})
