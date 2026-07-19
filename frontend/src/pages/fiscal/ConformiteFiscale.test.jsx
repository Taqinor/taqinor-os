import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../../api/fiscalApi', () => ({
  default: {
    tableauConformite: vi.fn(() => Promise.resolve({ data: [
      { obligation_id: 1, libelle: 'TVA mensuelle', statut: 'en_retard', prochaine_echeance: '2026-07-20' },
      { obligation_id: 2, libelle: 'IS acompte', statut: 'a_jour', prochaine_echeance: '2026-09-30' },
    ] })),
    echeances: vi.fn(() => Promise.resolve({ data: [
      { id: 10, libelle: 'TVA juin', date_limite: '2026-07-20', statut: 'a_preparer' },
    ] })),
  },
}))

import ConformiteFiscale from './ConformiteFiscale'

describe('ConformiteFiscale (WIR106)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('affiche le feu tricolore de conformité et les échéances', async () => {
    render(<ConformiteFiscale />)
    expect(await screen.findByText('TVA mensuelle')).toBeInTheDocument()
    expect(screen.getByText('En retard')).toBeInTheDocument()
    expect(screen.getByText('À jour')).toBeInTheDocument()
    // Échéances datées.
    expect(screen.getByText('TVA juin')).toBeInTheDocument()
    expect(screen.getByText('À préparer')).toBeInTheDocument()
  })
})
