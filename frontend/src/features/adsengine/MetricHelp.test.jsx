import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MetricHelp, { METRIC_HELP } from './MetricHelp'

/* PUB54 — Aide contextuelle FR statique : un « ? » cliquable/focusable
   affiche une explication en français simple, zéro dépendance. */

describe('MetricHelp (PUB54)', () => {
  it('rend rien pour une clé inconnue (jamais de contenu inventé)', () => {
    const { container } = render(<MetricHelp metric="inconnu_xyz" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('affiche le "?" fermé par défaut', () => {
    render(<MetricHelp metric="frequency" label="Fréquence" />)
    expect(screen.getByTestId('ae-metric-help-toggle-frequency')).toBeInTheDocument()
    expect(screen.queryByTestId('ae-metric-help-popover-frequency')).toBeNull()
  })

  it('cliquer ouvre le popover avec le texte FR statique', () => {
    render(<MetricHelp metric="cost_per_signature" label="Coût par signature" />)
    fireEvent.click(screen.getByTestId('ae-metric-help-toggle-cost_per_signature'))
    const popover = screen.getByTestId('ae-metric-help-popover-cost_per_signature')
    expect(popover).toHaveTextContent(METRIC_HELP.cost_per_signature)
  })

  it('re-cliquer referme le popover', () => {
    render(<MetricHelp metric="mer" />)
    const btn = screen.getByTestId('ae-metric-help-toggle-mer')
    fireEvent.click(btn)
    expect(screen.getByTestId('ae-metric-help-popover-mer')).toBeInTheDocument()
    fireEvent.click(btn)
    expect(screen.queryByTestId('ae-metric-help-popover-mer')).toBeNull()
  })

  it('porte un aria-label accessible dérivé du libellé', () => {
    render(<MetricHelp metric="cpl" label="Coût par lead" />)
    expect(screen.getByLabelText('Aide : Coût par lead')).toBeInTheDocument()
  })

  it('couvre toutes les métriques citées par PUB54 (MER, fréquence, apprentissage, coût par signature, junk rate)', () => {
    expect(METRIC_HELP.mer).toBeTruthy()
    expect(METRIC_HELP.frequency).toBeTruthy()
    expect(METRIC_HELP.learning).toBeTruthy()
    expect(METRIC_HELP.cost_per_signature).toBeTruthy()
    expect(METRIC_HELP.junk_rate).toBeTruthy()
  })
})
