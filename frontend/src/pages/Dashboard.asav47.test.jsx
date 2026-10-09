import { describe, it, expect } from 'vitest'
import { ticketsSlaEnRetard } from './Dashboard.jsx'

/* ASAV47 — la carte « tickets en retard de SLA » du tableau de bord compte les
   tickets dont le SERVEUR dit `sla_breach=true` (même source que la liste SAV),
   plus l'âge codé en dur 2/5/10 jours (`ticketSlaLevel === 'late'`).
   Test-du-test : remettre le filtre `ticketSlaLevel(t, now) === 'late'` ⇒ le
   ticket de 12 jours dans ses délais est compté et le ticket en retard serveur
   jeune ne l'est pas : le test échoue. */

const NOW = new Date('2026-07-20T09:00:00')

const tickets = [
  // En retard selon le serveur (SLA 24 h dépassé), ouvert depuis peu.
  { id: 1, statut: 'nouveau', priorite: 'normale', date_ouverture: '2026-07-19', sla_breach: true },
  // Très ancien (12 jours) mais DANS ses délais selon le serveur (SLA long / pause).
  { id: 2, statut: 'en_cours', priorite: 'normale', date_ouverture: '2026-07-08', sla_breach: false },
  // Société au SLA désactivé : le serveur ne pose jamais sla_breach.
  { id: 3, statut: 'nouveau', priorite: 'urgente', date_ouverture: '2026-07-01', sla_breach: false },
]

describe('ticketsSlaEnRetard (ASAV47)', () => {
  it('compte uniquement les tickets sla_breach=true', () => {
    expect(ticketsSlaEnRetard(tickets, NOW).map((t) => t.id)).toEqual([1])
  })

  it('un ticket ancien dans ses délais n\'est pas compté', () => {
    expect(ticketsSlaEnRetard(tickets, NOW).map((t) => t.id)).not.toContain(2)
  })

  it('un ticket d\'une société au SLA désactivé n\'est jamais compté', () => {
    expect(ticketsSlaEnRetard(tickets, NOW).map((t) => t.id)).not.toContain(3)
  })

  it('tolère une liste absente', () => {
    expect(ticketsSlaEnRetard(undefined)).toEqual([])
  })
})
