import { describe, it, expect } from 'vitest'
import {
  normalizeSyncStatus, syncStatusFor, formatAge, formatSyncDateTime,
} from './syncStatus'

/* PUB41 — fraîcheur + panne visibles : logique pure. */

describe('normalizeSyncStatus', () => {
  it('normalise une réponse complète', () => {
    const s = normalizeSyncStatus({
      types: [
        { type: 'insights', label: 'Insights', last_ok_at: '2026-07-18T10:00:00Z', age_minutes: 90, stale: false },
      ],
      stale: true,
      worst: { type: 'leads', label: 'Leads Meta', last_ok_at: '2026-07-01T00:00:00Z', age_minutes: 25000 },
    })
    expect(s.stale).toBe(true)
    expect(s.types).toHaveLength(1)
    expect(s.worst.type).toBe('leads')
  })

  it('réponse absente/malformée -> repli sûr, jamais une erreur', () => {
    expect(normalizeSyncStatus(null)).toEqual({ types: [], stale: false, worst: null })
    expect(normalizeSyncStatus(undefined)).toEqual({ types: [], stale: false, worst: null })
    expect(normalizeSyncStatus({})).toEqual({ types: [], stale: false, worst: null })
  })

  it('filtre les entrées vides du tableau types', () => {
    const s = normalizeSyncStatus({ types: [null, { type: 'a' }, undefined] })
    expect(s.types).toHaveLength(1)
  })
})

describe('syncStatusFor', () => {
  const status = normalizeSyncStatus({
    types: [
      { type: 'insights', label: 'Insights', age_minutes: 5 },
      { type: 'leads', label: 'Leads', age_minutes: 10 },
    ],
  })

  it('trouve le type demandé', () => {
    expect(syncStatusFor(status, 'leads').age_minutes).toBe(10)
  })

  it('type absent -> null (jamais fabriqué)', () => {
    expect(syncStatusFor(status, 'comments')).toBeNull()
  })

  it('status null -> null', () => {
    expect(syncStatusFor(null, 'leads')).toBeNull()
  })
})

describe('formatAge', () => {
  it('moins d’une heure -> minutes', () => {
    expect(formatAge(12)).toBe('12 min')
    expect(formatAge(59)).toBe('59 min')
  })
  it('moins de 48h -> heures', () => {
    expect(formatAge(90)).toBe('2 h')
    expect(formatAge(600)).toBe('10 h')
  })
  it('48h ou plus -> jours', () => {
    expect(formatAge(3000)).toBe('2 j')
  })
  it('valeur manquante -> chaîne vide (jamais NaN)', () => {
    expect(formatAge(null)).toBe('')
    expect(formatAge(undefined)).toBe('')
    expect(formatAge(NaN)).toBe('')
  })
})

describe('formatSyncDateTime', () => {
  it('formate en JJ/MM HH:MM', () => {
    const d = new Date(2026, 6, 18, 9, 5) // 18 juillet, 09:05 (heure locale)
    expect(formatSyncDateTime(d.toISOString())).toBe('18/07 09:05')
  })
  it('absent/invalide -> chaîne vide', () => {
    expect(formatSyncDateTime('')).toBe('')
    expect(formatSyncDateTime(null)).toBe('')
    expect(formatSyncDateTime('not-a-date')).toBe('')
  })
})
