import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BulkProductBar from './BulkProductBar.jsx'

/* ============================================================================
   WIR268/XSTK20/XPOS17 — « Cartes kanban » (deux-bacs, réservées à un
   emplacement précis) et « Étiquettes showroom » (jeton e-catalogue) : deux
   boutons additifs de la barre en masse, absents tant que le parent ne
   fournit pas le callback (StockList les gate — kanban sur un emplacement
   choisi, showroom toujours proposé mais message FR si aucun jeton).
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

describe('BulkProductBar — Étiquettes showroom (WIR268/XPOS17)', () => {
  it('absent sans onPrintShowroom', () => {
    render(<BulkProductBar {...baseProps} />)
    expect(screen.queryByRole('button', { name: /Étiquettes showroom/ })).toBeNull()
  })

  it('présent avec onPrintShowroom et appelle le callback au clic', async () => {
    const onPrintShowroom = vi.fn()
    render(<BulkProductBar {...baseProps} onPrintShowroom={onPrintShowroom} />)
    await userEvent.click(screen.getByRole('button', { name: /Étiquettes showroom/ }))
    expect(onPrintShowroom).toHaveBeenCalledTimes(1)
  })

  it('désactivé pendant showroomBusy', () => {
    render(<BulkProductBar {...baseProps} onPrintShowroom={vi.fn()} showroomBusy />)
    expect(screen.getByRole('button', { name: /Étiquettes showroom/ })).toBeDisabled()
  })
})
