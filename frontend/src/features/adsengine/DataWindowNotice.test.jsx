import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

/* ADSDEEP66 — Bandeau générique de fenêtre/limite de données : un preset par
   type (leads/insights/uniques/breakdowns/retention), variante alerte quand
   l'âge de la donnée approche la limite, message personnalisable. */

import DataWindowNotice from './DataWindowNotice'
import { DATA_WINDOWS } from './adsengine'

describe('DataWindowNotice (ADSDEEP66)', () => {
  it.each(Object.keys(DATA_WINDOWS))('rend le preset FR "%s" en variante info par défaut', (kind) => {
    render(<DataWindowNotice kind={kind} />)
    const notice = screen.getByTestId(`ae-data-window-${kind}`)
    expect(notice).toHaveAttribute('data-variant', 'info')
    expect(notice.textContent.length).toBeGreaterThan(10)
    expect(screen.queryByTestId(`ae-data-window-${kind}-alert`)).toBeNull()
  })

  it('leads : passe en alerte à 75 j (5/6 de 90 j), pas à 40 j', () => {
    const { rerender } = render(<DataWindowNotice kind="leads" ageDays={40} />)
    expect(screen.getByTestId('ae-data-window-leads')).toHaveAttribute('data-variant', 'info')
    rerender(<DataWindowNotice kind="leads" ageDays={80} />)
    expect(screen.getByTestId('ae-data-window-leads')).toHaveAttribute('data-variant', 'warning')
    expect(screen.getByTestId('ae-data-window-leads-alert')).toBeInTheDocument()
  })

  it('breakdowns : fenêtre 28 j, alerte proche de la limite', () => {
    render(<DataWindowNotice kind="breakdowns" ageDays={27} />)
    expect(screen.getByTestId('ae-data-window-breakdowns')).toHaveAttribute('data-variant', 'warning')
  })

  it('insights/uniques/retention : fenêtres en mois (37/13/13), pas d\'alerte loin de la limite', () => {
    render(<DataWindowNotice kind="insights" ageDays={30} />)
    expect(screen.getByTestId('ae-data-window-insights')).toHaveAttribute('data-variant', 'info')
    render(<DataWindowNotice kind="uniques" ageDays={30} />)
    expect(screen.getByTestId('ae-data-window-uniques')).toHaveAttribute('data-variant', 'info')
  })

  it('accepte un message personnalisé (override du preset)', () => {
    render(<DataWindowNotice kind="leads" message="Message sur mesure." testId="ae-custom" />)
    expect(screen.getByTestId('ae-custom')).toHaveTextContent('Message sur mesure.')
  })

  it('type inconnu sans message : ne rend rien (jamais un bandeau vide)', () => {
    const { container } = render(<DataWindowNotice kind="inconnu" />)
    expect(container).toBeEmptyDOMElement()
  })
})
