import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RobustesseBadges from './RobustesseBadges'

/* AOF101 — le « Done = » exige : seuils affichés À CÔTÉ des valeurs, et un
   test des deux états (sous le seuil / au-dessus du seuil). Rien n'est
   calculé ici : `marges` et `seuils` sont fournis tels quels par le moteur
   (`core/calepinage/types.py::Marges` / `Parametres.marge_*_min_m`). */

describe('RobustesseBadges — au-dessus du seuil', () => {
  it('affiche les deux marges EN CENTIMÈTRES avec leur seuil, sans alerte', () => {
    render(
      <RobustesseBadges
        marges={{ troncon_min_cm: 5, bande_min_cm: 8 }}
        seuils={{ troncon_min_cm: 2, bande_min_cm: 4 }}
      />,
    )
    expect(screen.getByText('Marge tronçon')).toBeInTheDocument()
    expect(screen.getByText(/5,0 cm/)).toBeInTheDocument()
    expect(screen.getByText(/seuil 2,0 cm/)).toBeInTheDocument()
    expect(screen.getByText('Marge bande')).toBeInTheDocument()
    expect(screen.getByText(/8,0 cm/)).toBeInTheDocument()
    expect(screen.getByText(/seuil 4,0 cm/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('RobustesseBadges — sous le seuil : badge d’alerte NOMMÉ', () => {
  it('affiche « calage au millimètre — non exploitable en chantier » quand la marge tronçon est sous le seuil', () => {
    const { container } = render(
      <RobustesseBadges
        marges={{ troncon_min_cm: 1, bande_min_cm: 8, rangee_critique: 'R12' }}
        seuils={{ troncon_min_cm: 2, bande_min_cm: 4 }}
      />,
    )
    expect(screen.getByRole('alert').textContent).toMatch(/calage au millimètre — non exploitable en chantier/)
    expect(container.querySelector('[data-marge-robustesse="Marge tronçon"]'))
      .toHaveAttribute('data-marge-sous-seuil', 'true')
    expect(container.querySelector('[data-marge-robustesse="Marge bande"]'))
      .toHaveAttribute('data-marge-sous-seuil', 'false')
    expect(screen.getByText(/Rangée la plus serrée : R12/)).toBeInTheDocument()
  })

  it('affiche DEUX alertes quand les deux marges sont sous leur seuil', () => {
    render(
      <RobustesseBadges
        marges={{ troncon_min_cm: 1, bande_min_cm: 2 }}
        seuils={{ troncon_min_cm: 2, bande_min_cm: 4 }}
      />,
    )
    expect(screen.getAllByRole('alert')).toHaveLength(2)
  })
})

describe('RobustesseBadges — cas dégénérés', () => {
  it('ne rend rien sans `marges`', () => {
    const { container } = render(<RobustesseBadges marges={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('ignore une marge absente au lieu d’afficher « NaN cm »', () => {
    render(<RobustesseBadges marges={{ troncon_min_cm: 5 }} seuils={{ troncon_min_cm: 2 }} />)
    expect(screen.getByText('Marge tronçon')).toBeInTheDocument()
    expect(screen.queryByText('Marge bande')).not.toBeInTheDocument()
  })
})
