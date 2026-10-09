import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BulkProductBar from './BulkProductBar.jsx'

// ASTK242 — codes de permission pilotables par test (null = tous portés).
const perms = vi.hoisted(() => ({ codes: null }))
vi.mock('../../features/stock/useVoitPrixAchat', () => {
  const porte = (c) => perms.codes === null || perms.codes.includes(c)
  return { usePermissionAchats: porte, useVoitPrixAchat: () => porte('prix_achat_voir'), default: () => porte('prix_achat_voir') }
})

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

describe('BulkProductBar — panneau Prix (ASTK242)', () => {
  beforeEach(() => { perms.codes = null })

  it('sans catalogue_prix_modifier : pas de panneau « Prix », aucun set_price', () => {
    perms.codes = ['stock_voir']
    const onAction = vi.fn()
    render(<BulkProductBar {...baseProps} onAction={onAction} />)
    expect(screen.queryByText('Prix')).toBeNull()
    expect(onAction).not.toHaveBeenCalled()
  })

  it('avec catalogue_prix_modifier : le panneau « Prix » est offert', () => {
    perms.codes = ['catalogue_prix_modifier']
    render(<BulkProductBar {...baseProps} />)
    expect(screen.getByText('Prix')).toBeInTheDocument()
  })
})

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
