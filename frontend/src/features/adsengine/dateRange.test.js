import { describe, it, expect } from 'vitest'
import {
  DATE_RANGE_PRESETS, toISODate, presetRange, rangeLengthDays,
  previousRange, computeDelta, formatDeltaPct,
} from './dateRange'

/* PUB40 — sélecteur de période + comparaison : logique pure. */

describe('DATE_RANGE_PRESETS', () => {
  it('expose les 4 presets attendus (hier/7j/30j/personnalisé)', () => {
    expect(DATE_RANGE_PRESETS.map(p => p.key)).toEqual(
      ['hier', '7j', '30j', 'personnalise'])
  })
})

describe('toISODate', () => {
  it('formate en YYYY-MM-DD, calendaire local (jamais UTC)', () => {
    expect(toISODate(new Date(2026, 6, 5))).toBe('2026-07-05') // 5 juillet
  })
})

describe('presetRange', () => {
  const today = new Date(2026, 6, 19) // 19 juillet 2026 (dimanche)

  it('« hier » = un seul jour, la veille', () => {
    const r = presetRange('hier', today)
    expect(r).toEqual({ debut: '2026-07-18', fin: '2026-07-18' })
  })

  it('« 7j » = 7 jours glissants incluant aujourd’hui', () => {
    const r = presetRange('7j', today)
    expect(r).toEqual({ debut: '2026-07-13', fin: '2026-07-19' })
    expect(rangeLengthDays(r)).toBe(7)
  })

  it('« 30j » = 30 jours glissants incluant aujourd’hui', () => {
    const r = presetRange('30j', today)
    expect(r).toEqual({ debut: '2026-06-20', fin: '2026-07-19' })
    expect(rangeLengthDays(r)).toBe(30)
  })

  it('« personnalise » ne résout rien (null — l’écran garde la saisie)', () => {
    expect(presetRange('personnalise', today)).toBeNull()
  })

  it('preset inconnu -> null (jamais une erreur)', () => {
    expect(presetRange('nope', today)).toBeNull()
  })
})

describe('rangeLengthDays', () => {
  it('un seul jour -> 1', () => {
    expect(rangeLengthDays({ debut: '2026-07-18', fin: '2026-07-18' })).toBe(1)
  })
  it('bornes manquantes -> null', () => {
    expect(rangeLengthDays({})).toBeNull()
    expect(rangeLengthDays({ debut: '2026-07-18' })).toBeNull()
  })
})

describe('previousRange (doctrine PUB40)', () => {
  it('1 jour -> même jour, semaine précédente (-7 j)', () => {
    const prev = previousRange({ debut: '2026-07-18', fin: '2026-07-18' })
    expect(prev).toEqual({ debut: '2026-07-11', fin: '2026-07-11' })
  })

  it('7 jours -> période équivalente immédiatement précédente', () => {
    const prev = previousRange({ debut: '2026-07-10', fin: '2026-07-16' })
    expect(prev).toEqual({ debut: '2026-07-03', fin: '2026-07-09' })
  })

  it('30 jours -> même longueur, immédiatement avant', () => {
    const current = { debut: '2026-06-01', fin: '2026-06-30' }
    const prev = previousRange(current)
    expect(rangeLengthDays(prev)).toBe(rangeLengthDays(current))
    expect(prev.fin).toBe('2026-05-31')
  })

  it('bornes absentes -> null', () => {
    expect(previousRange({})).toBeNull()
  })
})

describe('computeDelta', () => {
  it('calcule le delta et le pourcentage', () => {
    const d = computeDelta(120, 100)
    expect(d.delta).toBe(20)
    expect(d.pct).toBeCloseTo(20)
    expect(d.direction).toBe('up')
  })

  it('baisse -> direction down, pct négatif', () => {
    const d = computeDelta(80, 100)
    expect(d.pct).toBeCloseTo(-20)
    expect(d.direction).toBe('down')
  })

  it('précédent nul -> pct null (jamais une division par zéro fabriquée)', () => {
    const d = computeDelta(50, 0)
    expect(d.delta).toBe(50)
    expect(d.pct).toBeNull()
  })

  it('valeur manquante -> tout null, direction flat', () => {
    expect(computeDelta(null, 100)).toEqual({ delta: null, pct: null, direction: 'flat' })
    expect(computeDelta(100, null)).toEqual({ delta: null, pct: null, direction: 'flat' })
  })

  it('accepte des strings numériques (Decimal sérialisé par l’API)', () => {
    const d = computeDelta('120.00', '100.00')
    expect(d.pct).toBeCloseTo(20)
  })

  it('égalité -> direction flat, pct 0', () => {
    const d = computeDelta(100, 100)
    expect(d.pct).toBe(0)
    expect(d.direction).toBe('flat')
  })
})

describe('formatDeltaPct', () => {
  it('positif -> signe +', () => {
    expect(formatDeltaPct(12.34)).toBe('+12.3 %')
  })
  it('négatif -> signe − (moins typographique)', () => {
    expect(formatDeltaPct(-8)).toBe('−8 %')
  })
  it('null/NaN -> tiret cadratin', () => {
    expect(formatDeltaPct(null)).toBe('—')
    expect(formatDeltaPct(undefined)).toBe('—')
    expect(formatDeltaPct(NaN)).toBe('—')
  })
})
