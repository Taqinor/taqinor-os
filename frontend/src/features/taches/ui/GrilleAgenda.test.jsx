import { render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import GrilleAgenda from './GrilleAgenda'

/* R4-40 — la Semaine : en-têtes de jours d'un seul dessin, « 0 faite » tu, grille ouverte près de maintenant.
   Nouveau fichier : aucun test n'existait pour la grille (seuls les tests d'écran de l'Agenda la traversaient). */

const JOURS = [
  { jour: '2026-11-16', ouvre: true, faites_nb: 0 },
  { jour: '2026-11-17', ouvre: true, faites_nb: 3 },
  { jour: '2026-11-19', ouvre: true },
  { jour: '2026-11-21', ouvre: false, faites_nb: 0 }, // week-end vide : colonne étroite
  { jour: '2026-11-22', ouvre: false, blocs: [{ id: 9, titre: 'Visite', heure_debut: '10:00', estimation_minutes: 60 }] }, // week-end chargé
]
const NOMS = { '2026-11-16': 'lun. 16', '2026-11-17': 'mar. 17', '2026-11-19': 'jeu. 19', '2026-11-21': 'sam. 21', '2026-11-22': 'dim. 22' }

const monter = (props = {}) => render(
  <GrilleAgenda jours={JOURS} aujourdhui="2026-11-19" nomsJours={NOMS} onCreneau={() => {}} {...props} />,
)

afterEach(() => { vi.unstubAllGlobals() })

describe('R4-40 — en-têtes de jours de la Semaine', () => {
  it('« 0 faite » ne s\'écrit pas ; un compte positif sur un jour passé, si', () => {
    const { container } = monter()
    const tetes = container.querySelectorAll('.semaine-tete > div')
    // la 1re cellule est la gouttière des heures
    expect(tetes[1].querySelector('.ag-faites')).toBeNull() // lun. 16 : 0 faite
    expect(tetes[2].querySelector('.ag-faites')).toHaveTextContent('3 faites')
    expect(tetes[3].querySelector('.ag-faites')).toBeNull() // aujourd'hui
    expect(container.querySelectorAll('.semaine-tete .ag-faites')).toHaveLength(1)
  })

  it('une colonne étroite (week-end vide) porte `.etroit` ; un week-end chargé est dessiné comme les autres jours', () => {
    const { container } = monter()
    const tetes = [...container.querySelectorAll('.semaine-tete > div')]
    expect(tetes[4]).toHaveClass('repos', 'etroit') // sam. 21 : vide
    expect(tetes[5]).toHaveClass('repos')
    expect(tetes[5]).not.toHaveClass('etroit') // dim. 22 : une visite → colonne entière
    expect(tetes[1]).not.toHaveClass('etroit')
  })
})

describe('R4-40 — la grille s\'ouvre près de maintenant (bureau)', () => {
  /** Un cadre défilant (la page de l'ERP) de 600 px visibles : la ligne « maintenant » est à `ligneTop` px du haut de l'écran. */
  function dansUnCadre(ligneTop) {
    vi.stubGlobal('matchMedia', (q) => ({ matches: q === '(min-width: 769px)', media: q, addEventListener() {}, removeEventListener() {} }))
    const cadre = document.createElement('div')
    cadre.style.overflowY = 'auto'
    Object.defineProperty(cadre, 'scrollHeight', { value: 2000, configurable: true })
    Object.defineProperty(cadre, 'clientHeight', { value: 600, configurable: true })
    cadre.getBoundingClientRect = () => ({ top: 100, bottom: 700, height: 600, left: 0, right: 1000, width: 1000 })
    document.body.appendChild(cadre)
    const posteur = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function boite() {
      if (this === cadre) return { top: 100, bottom: 700, height: 600, left: 0, right: 1000, width: 1000 }
      if (this.classList?.contains('maintenant')) return { top: ligneTop, bottom: ligneTop + 2, height: 2, left: 0, right: 100, width: 100 }
      return { top: 0, bottom: 56, height: 56, left: 0, right: 100, width: 100 }
    })
    return { cadre, posteur }
  }

  it('la ligne « maintenant » hors de vue : la page défile pour la poser à 40 % de la hauteur visible', () => {
    const { cadre } = dansUnCadre(1500)
    const { container } = render(
      <GrilleAgenda jours={JOURS} aujourdhui="2026-11-19" maintenant={new Date(2026, 10, 19, 17, 30)} nomsJours={NOMS} onCreneau={() => {}} />,
      { container: cadre.appendChild(document.createElement('div')) },
    )
    expect(container.querySelector('.maintenant')).not.toBeNull()
    // 1500 - (100 + (600 - 56) * 0,4 + 56) = 1126,4
    expect(cadre.scrollTop).toBeCloseTo(1126.4, 1)
    cadre.remove()
  })

  it('la ligne déjà en vue : rien ne bouge', () => {
    const { cadre } = dansUnCadre(300)
    render(
      <GrilleAgenda jours={JOURS} aujourdhui="2026-11-19" maintenant={new Date(2026, 10, 19, 10, 0)} nomsJours={NOMS} onCreneau={() => {}} />,
      { container: cadre.appendChild(document.createElement('div')) },
    )
    expect(cadre.scrollTop).toBe(0)
    cadre.remove()
  })

  it('sur iPhone (< 769 px) : jamais de défilement automatique', () => {
    const { cadre } = dansUnCadre(1500)
    vi.stubGlobal('matchMedia', (q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }))
    render(
      <GrilleAgenda jours={JOURS} aujourdhui="2026-11-19" maintenant={new Date(2026, 10, 19, 17, 30)} nomsJours={NOMS} onCreneau={() => {}} />,
      { container: cadre.appendChild(document.createElement('div')) },
    )
    expect(cadre.scrollTop).toBe(0)
    cadre.remove()
  })
})
