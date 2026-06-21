import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { GarantiePill } from './EquipementsPage.jsx'
import { GARANTIE_ETATS, garantieLabel } from '../../features/sav/equipement'

/* J144 — refonte SAV : le parc d'équipements passe à StatusPill + DataTable.
   On verrouille la brique de présentation de l'état de garantie : ton + libellé
   FR explicite (la couleur n'est jamais le seul signal). */

const DOT_CLASS = {
  neutral: 'bg-muted-foreground', success: 'bg-success',
  warning: 'bg-warning', danger: 'bg-destructive',
}

describe('GarantiePill (J144 — état de garantie → ton + libellé FR)', () => {
  it('chaque état de garantie connu rend un libellé FR et un point coloré', () => {
    for (const etat of Object.keys(GARANTIE_ETATS)) {
      const { container, unmount } = render(<GarantiePill eq={{ garantie_etat: etat }} />)
      const hasKnownDot = Object.values(DOT_CLASS)
        .some((cls) => container.querySelector(`.${cls}`))
      expect(hasKnownDot).toBe(true)
      unmount()
    }
  })

  it('affiche le libellé FR « Hors garantie »', () => {
    render(<GarantiePill eq={{ garantie_etat: 'hors_garantie' }} />)
    expect(screen.getByText(garantieLabel({ garantie_etat: 'hors_garantie' }))).toBeInTheDocument()
  })

  it('rend le point coloré correspondant au ton (sous garantie → succès)', () => {
    const { container } = render(
      <GarantiePill eq={{ garantie_etat: 'sous_garantie', date_fin_garantie: '2030-01-01' }} />,
    )
    expect(container.querySelector(`.${DOT_CLASS.success}`)).toBeTruthy()
  })

  it('état manquant → ton neutre + libellé « non renseignée »', () => {
    const { container } = render(<GarantiePill eq={{}} />)
    expect(container.querySelector(`.${DOT_CLASS.neutral}`)).toBeTruthy()
    expect(screen.getByText(/non renseignée/i)).toBeInTheDocument()
  })
})
