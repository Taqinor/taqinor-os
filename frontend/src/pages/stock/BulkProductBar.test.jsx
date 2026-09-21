import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BulkProductBar from './BulkProductBar.jsx'

/* ============================================================================
   WIR268/XSTK20 — « Cartes kanban » (deux-bacs, réservées à un emplacement
   précis) : bouton additif de la barre en masse, absent tant que le parent
   ne fournit pas le callback (StockList le gate sur un emplacement choisi).
   SOLMVP41 — « Étiquettes showroom » (WIR268/XPOS17, jeton e-catalogue de
   `apps.compta.EcatalogueBoutique`) est partie avec compta (Groupe SOLMVP).
   ========================================================================== */

const baseProps = {
  count: 2,
  categories: [],
  marques: [],
  busy: false,
  onAction: vi.fn(),
  onExport: vi.fn(),
  onClear: vi.fn(),
}

describe('BulkProductBar — Cartes kanban (WIR268/XSTK20)', () => {
  it('absent sans onPrintKanban (ex. aucun emplacement filtré)', () => {
    render(<BulkProductBar {...baseProps} />)
    expect(screen.queryByRole('button', { name: /Cartes kanban/ })).toBeNull()
  })

  it('présent avec onPrintKanban et appelle le callback au clic', async () => {
    const onPrintKanban = vi.fn()
    render(<BulkProductBar {...baseProps} onPrintKanban={onPrintKanban} />)
    await userEvent.click(screen.getByRole('button', { name: /Cartes kanban/ }))
    expect(onPrintKanban).toHaveBeenCalledTimes(1)
  })

  it('désactivé pendant kanbanBusy', () => {
    render(<BulkProductBar {...baseProps} onPrintKanban={vi.fn()} kanbanBusy />)
    expect(screen.getByRole('button', { name: /Cartes kanban/ })).toBeDisabled()
  })
})
