import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BulkProductBar from './BulkProductBar.jsx'

// ASTK242 — le gating par codes lit le store : ici l'auto-accord (compte
// légacy sans rôle fin) ; les cas « sans code » sont dans ModelesBcf.test.jsx.
vi.mock('../../features/stock/useVoitPrixAchat', () => ({
  usePermissionAchats: () => true,
  useVoitPrixAchat: () => true,
}))

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

describe('BulkProductBar — export serveur (ADRG24)', () => {
  it('sans onExport (pas de `stock_export`) : pas d’Exporter Excel', () => {
    render(<BulkProductBar {...baseProps} onExport={null} />)
    expect(screen.queryByRole('button', { name: /Exporter Excel/ })).toBeNull()
  })

  it('avec onExport : Exporter Excel présent', () => {
    render(<BulkProductBar {...baseProps} />)
    expect(screen.getByRole('button', { name: /Exporter Excel/ })).toBeInTheDocument()
  })
})

describe('BulkProductBar — suggestions de marque (ASUP52)', () => {
  it('ne propose pas une marque archivée', async () => {
    const marques = [
      { id: 1, nom: 'Huawei', archived: false },
      { id: 2, nom: 'Ancienne', archived: true },
    ]
    const { container } = render(<BulkProductBar {...baseProps} count={3} marques={marques} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Marque' }))
    const suggestions = [...container.querySelectorAll('#bpb-marques option')].map((o) => o.value)
    expect(suggestions).toEqual(['Huawei'])
    expect(screen.getByPlaceholderText('Marque')).not.toBeDisabled() // saisie libre conservée
  })
})

describe('BulkProductBar — variation de prix confirmée et rejouable (ACNC24)', () => {
  it('« Appliquer » confirme « 2 produits — ex. 1 000,00 → 1 100,00 » ; même clé après un échec, valeur vidée au succès', async () => {
    const onAction = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true)
    render(<BulkProductBar {...baseProps} prixExemple="1000.00" onAction={onAction} />)
    const prix = async (ouvrir = true) => {
      if (ouvrir) await userEvent.click(screen.getByRole('radio', { name: 'Prix' }))
      await userEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
      expect(screen.getByRole('alert')).toHaveTextContent(/2 produits — ex\. 1\s?000,00 → 1\s?100,00/)
      await userEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    }
    await userEvent.click(screen.getByRole('radio', { name: 'Prix' }))
    await userEvent.type(screen.getByPlaceholderText('ex. 10 ou -5'), '10')
    await prix(false)
    expect(onAction).toHaveBeenCalledTimes(1)
    await prix()
    expect(onAction).toHaveBeenCalledTimes(2)
    const [premier, second] = onAction.mock.calls.map(([, p]) => p.idempotencyKey)
    expect(premier).toBeTruthy()
    expect(second).toBe(premier)
    expect(onAction.mock.calls[0][1]).toMatchObject({ mode: 'percent', valeur: '10' })
    await userEvent.click(screen.getByRole('radio', { name: 'Prix' }))
    expect(screen.getByPlaceholderText('ex. 10 ou -5')).toHaveValue(null)
  })
})

