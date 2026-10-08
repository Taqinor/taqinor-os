import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* APAR32 — le journal d'audit des réglages se lit sur toute la rétention :
   « Charger plus » ajoute la page suivante (offset = `next` du serveur)
   jusqu'à épuisement — la ligne n°51 devient atteignable depuis l'écran. */

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

const { getAudit } = vi.hoisted(() => {
  const ligne = (n) => ({
    id: n, field: `f${n}`, field_label: `Ligne ${n}`, section: 'profil',
    old_value: 'a', new_value: 'b', user_nom: 'X', timestamp: '2026-10-08T10:00:00Z',
  })
  const getAudit = vi.fn((params) => {
    const debut = params.offset ?? 0
    const fin = Math.min(debut + params.limit, 60)
    const results = []
    for (let n = debut + 1; n <= fin; n += 1) results.push(ligne(n))
    return Promise.resolve({ data: { count: 60, results, next: fin < 60 ? fin : null } })
  })
  return { getAudit }
})
vi.mock('../../api/parametresApi', () => ({
  default: {
    getAudit: (p) => getAudit(p),
    getAuditSections: () => Promise.resolve({ data: { sections: [] } }),
  },
}))

import SettingsAuditFeed from './SettingsAuditFeed'

describe('APAR32 — Charger plus', () => {
  afterEach(() => { cleanup(); getAudit.mockClear() })

  it('la ligne 51 est atteignable, puis le bouton disparaît', async () => {
    render(<SettingsAuditFeed limit={50} />)
    await screen.findByText('Ligne 50')
    expect(screen.queryByText('Ligne 51')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Charger plus/ }))
    await screen.findByText('Ligne 51')
    expect(getAudit).toHaveBeenLastCalledWith({ limit: 50, offset: 50 })
    expect(screen.getByText('Ligne 1')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('button', { name: /Charger plus/ })).not.toBeInTheDocument())
  })
})
