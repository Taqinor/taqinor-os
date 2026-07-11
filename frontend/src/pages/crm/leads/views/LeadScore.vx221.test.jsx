import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ScoreBadge, { scoreTooltip } from '../../../../features/crm/ScoreBadge'

/* VX221 — le score de lead dit POURQUOI : le badge expose un tooltip des 2-3
   facteurs dominants, construit depuis la décomposition score_reasons du
   backend, et un badge score apparaît sur la carte kanban (LeadCard). */

afterEach(() => { cleanup() })

describe('scoreTooltip (VX221)', () => {
  it('liste les 3 facteurs dominants avec leurs points', () => {
    const lead = {
      score: 55,
      score_reasons: [
        { facteur: 'facture', label: 'Facture élevée', points: 20 },
        { facteur: 'canal', label: 'Canal', points: 15 },
        { facteur: 'recency', label: 'Lead récent', points: 12 },
        { facteur: 'type', label: "Type d'installation", points: 8 },
      ],
    }
    const tip = scoreTooltip(lead)
    expect(tip).toContain('55/100')
    expect(tip).toContain('+20 Facture élevée')
    expect(tip).toContain('+15 Canal')
    expect(tip).toContain('+12 Lead récent')
    // Seuls les 3 premiers facteurs (type=+8 exclu).
    expect(tip).not.toContain("+8 Type d'installation")
  })

  it('retombe sur le libellé simple sans décomposition', () => {
    expect(scoreTooltip({ score: 40 })).toBe('Score de qualité : 40/100')
    expect(scoreTooltip({ score: 40, score_reasons: [] }))
      .toBe('Score de qualité : 40/100')
  })
})

describe('ScoreBadge partagé (VX221)', () => {
  it('affiche le score sur la carte avec le tooltip des raisons', () => {
    render(<ScoreBadge lead={{
      score: 72,
      score_label: 'Chaud',
      score_reasons: [
        { facteur: 'facture', label: 'Facture élevée', points: 20 },
        { facteur: 'recency', label: 'Lead récent', points: 12 },
      ],
    }} />)
    const badge = screen.getByText('72')
    expect(badge).toBeInTheDocument()
    expect(badge.getAttribute('title')).toContain('+20 Facture élevée')
    expect(badge.getAttribute('title')).toContain('+12 Lead récent')
  })

  it('ne rend rien sans score', () => {
    const { container } = render(<ScoreBadge lead={{ score: null }} />)
    expect(container.querySelector('.lv-score-badge')).toBeNull()
  })
})
