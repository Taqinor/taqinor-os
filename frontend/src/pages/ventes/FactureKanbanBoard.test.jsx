import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import FactureKanbanBoard from './FactureKanbanBoard'

function wrap(ui) {
  return <ThemeProvider>{ui}</ThemeProvider>
}

const TODAY = '2026-07-05'

describe('FactureKanbanBoard (ZFAC9)', () => {
  it('regroupe les factures par colonne avec compteur + total MAD', () => {
    const factures = [
      { id: 1, reference: 'FAC-001', statut: 'brouillon', total_ttc: 1000, client_nom: 'Client A' },
      { id: 2, reference: 'FAC-002', statut: 'emise', date_echeance: '2020-01-01', total_ttc: 2000, client_nom: 'Client B' },
      { id: 3, reference: 'FAC-003', statut: 'payee', montant_paye: 500, montant_du: 0, total_ttc: 500, client_nom: 'Client C' },
    ]
    render(wrap(<FactureKanbanBoard factures={factures} today={TODAY} />))

    expect(screen.getByTestId('fkb-count-brouillon')).toHaveTextContent('1')
    expect(screen.getByTestId('fkb-count-en_retard')).toHaveTextContent('1')
    expect(screen.getByTestId('fkb-count-payee')).toHaveTextContent('1')
    expect(screen.getByTestId('fkb-total-brouillon')).toHaveTextContent('1 000')
    expect(screen.getByText('FAC-001')).toBeInTheDocument()
    expect(screen.getByText('FAC-002')).toBeInTheDocument()
  })

  it('une facture annulée n’apparaît dans aucune colonne', () => {
    const factures = [{ id: 9, reference: 'FAC-009', statut: 'annulee', total_ttc: 999 }]
    render(wrap(<FactureKanbanBoard factures={factures} today={TODAY} />))
    expect(screen.queryByText('FAC-009')).not.toBeInTheDocument()
  })

  it('cliquer une carte appelle onOpenFacture avec la facture (même action que la ligne de la liste)', async () => {
    const onOpenFacture = vi.fn()
    const factures = [{ id: 1, reference: 'FAC-001', statut: 'brouillon', total_ttc: 100 }]
    render(wrap(<FactureKanbanBoard factures={factures} today={TODAY} onOpenFacture={onOpenFacture} />))
    await userEvent.click(screen.getByText('FAC-001'))
    expect(onOpenFacture).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })

  it('ne plante pas avec une liste vide/undefined', () => {
    render(wrap(<FactureKanbanBoard factures={[]} today={TODAY} />))
    expect(screen.getByTestId('facture-kanban-board')).toBeInTheDocument()
    render(wrap(<FactureKanbanBoard today={TODAY} />))
  })

  it('VX142(d) — carte sans StatusPill redondant : montre l\'échéance quand connue', () => {
    const factures = [
      { id: 2, reference: 'FAC-002', statut: 'emise', date_echeance: '2020-01-01', total_ttc: 2000, client_nom: 'Client B' },
    ]
    render(wrap(<FactureKanbanBoard factures={factures} today={TODAY} />))
    // La rangée référence+info de la carte ne contient plus le point coloré
    // du StatusPill (aria-hidden) ; la date d'échéance apparaît à la place.
    const refRow = screen.getByText('FAC-002').closest('div')
    expect(refRow.querySelector('.rounded-full.size-1\\.5, [class*="size-1.5"]')).toBeNull()
    expect(screen.getByText('01/01/2020')).toBeInTheDocument()
  })

  it('VX142(d) — carte sans échéance montre le montant dû à la place', () => {
    const factures = [
      { id: 4, reference: 'FAC-004', statut: 'emise', montant_du: 750, total_ttc: 750, client_nom: 'Client D' },
    ]
    render(wrap(<FactureKanbanBoard factures={factures} today={TODAY} />))
    expect(screen.getByText(/Dû/)).toBeInTheDocument()
  })
})
