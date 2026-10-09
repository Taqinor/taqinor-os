import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

// ASAV46 — le ton « en retard » du badge SLA vient du serveur (`sla_breach`),
// l'âge reste neutre. Cas : 12 j d'âge dans les délais ; 3 j mais dépassé
// serveur ; sans échéance (SLA désactivé).

vi.mock('../../api/savApi', () => ({ default: {} }))
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/installationsApi', () => ({ default: {} }))

import { TicketSlaBadge, TicketSlaEcheanceChip } from './TicketsPage'

beforeEach(() => { vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date('2026-10-09T10:00:00')) })
afterEach(() => { cleanup(); vi.useRealTimers() })

const base = { statut: 'en_cours', priorite: 'normale', annule: false }
const rouge = (el) => /destructive/.test(el.closest('span,div').className)

function rendre(ticket) {
  return render(<><TicketSlaBadge ticket={ticket} /><TicketSlaEcheanceChip ticket={ticket} /></>)
}

describe('ASAV46 — badge SLA : ton du serveur', () => {
  it('12 j d\'âge, échéance dans 18 j, sla_breach=false : neutre, jamais rouge', () => {
    rendre({ ...base, date_ouverture: '2026-09-27', sla_breach: false, sla_due_at_effectif: '2026-10-27' })
    expect(rouge(screen.getByText(/ouvert depuis 12 j/))).toBe(false)
    expect(screen.getByText(/à résoudre sous 18 j/)).toBeInTheDocument()
    expect(screen.queryByText(/SLA dépassé/)).toBeNull()
  })

  it('3 j d\'âge mais sla_breach=true : rouge « SLA dépassé »', () => {
    rendre({ ...base, date_ouverture: '2026-10-06', sla_breach: true, sla_due_at_effectif: '2026-10-07' })
    expect(rouge(screen.getByText(/ouvert depuis 3 j/))).toBe(true)
    expect(screen.getAllByText(/SLA dépassé/).length).toBeGreaterThan(0)
  })

  it('sans échéance (SLA désactivé) : aucun rouge SLA, même après 30 j', () => {
    rendre({ ...base, date_ouverture: '2026-09-09', sla_breach: false, sla_due_at_effectif: null })
    expect(rouge(screen.getByText(/ouvert depuis 30 j/))).toBe(false)
    expect(screen.queryByText(/SLA dépassé/)).toBeNull()
  })
})
