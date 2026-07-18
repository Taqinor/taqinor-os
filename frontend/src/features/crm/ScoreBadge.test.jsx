import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ScoreBadge, { scoreTooltip } from './ScoreBadge'

/* LW17 — la prop `asTrigger` est ADDITIVE : le rendu par défaut (span) reste
   identique pour les consommateurs existants (kanban/liste). */

afterEach(() => cleanup())

describe('LW17 — ScoreBadge (prop additive asTrigger)', () => {
  it('rendu par défaut : un <span> .lv-score-badge avec le score (inchangé)', () => {
    const { container } = render(<ScoreBadge lead={{ score: 72, score_label: 'Chaud' }} />)
    const el = container.querySelector('.lv-score-badge')
    expect(el).toBeInTheDocument()
    expect(el.tagName).toBe('SPAN')
    expect(el).toHaveTextContent('72')
  })

  it('asTrigger : rendu en <button> avec aria-label descriptif', () => {
    render(<ScoreBadge lead={{ score: 72, score_label: 'Chaud' }} asTrigger />)
    const btn = screen.getByRole('button', { name: /Score de qualité 72/ })
    expect(btn.tagName).toBe('BUTTON')
  })

  it('sans score : « — » en .lv-muted (inchangé)', () => {
    const { container } = render(<ScoreBadge lead={{}} />)
    const el = container.querySelector('.lv-muted')
    expect(el).toBeInTheDocument()
    expect(el).toHaveTextContent('—')
  })

  it('scoreTooltip garde ses 3 facteurs dominants', () => {
    const tip = scoreTooltip({
      score: 72,
      score_reasons: [
        { label: 'Facture élevée', points: 20 },
        { label: 'Canal', points: 15 },
        { label: 'Lead récent', points: 12 },
      ],
    })
    expect(tip).toContain('+20 Facture élevée')
    expect(tip).toContain('+15 Canal')
  })
})
