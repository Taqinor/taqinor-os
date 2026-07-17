import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

/* ADSDEEP23 — Bandeau rétention 90 j : notice FR permanente + alerte quand le
   pull approche la fenêtre. */

import LeadRetentionNotice from './LeadRetentionNotice'

describe('LeadRetentionNotice (ADSDEEP23)', () => {
  it('rend la notice FR permanente (variante info par défaut)', () => {
    render(<LeadRetentionNotice />)
    const notice = screen.getByTestId('ae-lead-retention-notice')
    expect(notice).toHaveTextContent(/Meta efface les leads après 90 jours/)
    expect(notice).toHaveTextContent(/ERP\/Odoo/)
    expect(notice).toHaveAttribute('data-variant', 'info')
    expect(screen.queryByTestId('ae-lead-retention-alert')).toBeNull()
  })

  it('passe en alerte quand le plus vieux lead approche 90 j', () => {
    render(<LeadRetentionNotice oldestLeadAgeDays={80} />)
    const notice = screen.getByTestId('ae-lead-retention-notice')
    expect(notice).toHaveAttribute('data-variant', 'warning')
    expect(screen.getByTestId('ae-lead-retention-alert')).toBeInTheDocument()
  })

  it('reste en info sous le seuil', () => {
    render(<LeadRetentionNotice oldestLeadAgeDays={40} />)
    expect(screen.getByTestId('ae-lead-retention-notice'))
      .toHaveAttribute('data-variant', 'info')
  })
})
