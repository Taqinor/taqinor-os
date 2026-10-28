// RGEN3 / RGEN9 — les deux bandeaux résidentiels (module neuf : composants neufs).
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import BandeauGrandSysteme from './BandeauGrandSysteme'
import BandeauTailleLead from './BandeauTailleLead'
import { ETAT_INITIAL } from '../../../../features/ventes/quote/sizingReducer'

describe('BandeauGrandSysteme (RGEN9, décision du 23/10)', () => {
  it('se tait jusqu’à 120 panneaux, même au-delà de 36 kWc', () => {
    render(<BandeauGrandSysteme modeInstallation="residentiel" nbPanneaux="88" kwp={62.48} />)
    expect(screen.queryByTestId('gen-grand-systeme')).toBeNull()
  })
  it('signale une étude sur mesure au-delà de 120 panneaux, sans renvoyer au C&I', () => {
    render(<BandeauGrandSysteme modeInstallation="residentiel" nbPanneaux="264" kwp={187.44} />)
    const b = screen.getByTestId('gen-grand-systeme')
    expect(b.textContent).toMatch(/264 panneaux/)
    expect(b.textContent).toMatch(/étude sur mesure est conseillée/)
    expect(b.textContent).not.toMatch(/Industriel|Commercial/)
  })
  it('ne s’affiche jamais hors résidentiel', () => {
    render(<BandeauGrandSysteme modeInstallation="industriel" nbPanneaux="300" kwp={213} />)
    expect(screen.queryByTestId('gen-grand-systeme')).toBeNull()
  })
})

describe('BandeauTailleLead (RGEN3)', () => {
  it('dit la taille demandée sur la fiche', () => {
    render(<BandeauTailleLead sizing={{ ...ETAT_INITIAL, tailleLead: 16 }} />)
    expect(screen.getByTestId('gen-taille-lead').textContent).toMatch(/16 kWc/)
  })
  it('se tait quand la taille ne vient pas de la fiche', () => {
    render(<BandeauTailleLead sizing={ETAT_INITIAL} />)
    expect(screen.queryByTestId('gen-taille-lead')).toBeNull()
  })
})
