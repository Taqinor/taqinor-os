// NTMOB24 — badge hors-ligne PAR ENREGISTREMENT (liste chantiers/leads/stock).
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

import OfflinePendingBadge from './OfflinePendingBadge'

// La file terrain tire `installationsApi` (axios) : on la bouchonne, le hook
// n'a besoin que de `pending()`.
const fieldOutbox = { pending: vi.fn(async () => []) }
vi.mock('../../features/installations/offline/fieldOutbox', () => ({ fieldOutbox }))

const { useOfflinePending } = await import('./useOfflinePending')
const { queueOperation, purgeModuleOutboxes } = await import('../../lib/offlineOutbox')

function Liste({ champ }) {
  const compte = useOfflinePending('crm', champ ? { champ } : undefined)
  return (
    <ul>
      {[7, 9].map((id) => (
        <li key={id} data-testid={`ligne-${id}`}>
          {`Lead ${id}`}
          <OfflinePendingBadge n={compte.get(String(id)) || 0} />
        </li>
      ))}
    </ul>
  )
}

describe('OfflinePendingBadge', () => {
  beforeEach(async () => {
    fieldOutbox.pending.mockResolvedValue([])
    await purgeModuleOutboxes()
  })
  afterEach(async () => { await purgeModuleOutboxes() })

  it('reste invisible quand rien n’attend (aucun bruit permanent)', () => {
    const { container } = render(<OfflinePendingBadge n={0} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('annonce le nombre de modifications non synchronisées', () => {
    render(<OfflinePendingBadge n={3} />)
    const badge = screen.getByTestId('offline-pending-badge')
    expect(badge).toHaveAttribute('aria-label', 'Modifications non synchronisées : 3')
    expect(badge).toHaveTextContent('3')
  })

  it('se pose sur LA ligne concernée et se met à jour à la mise en file', async () => {
    render(<Liste />)
    expect(screen.queryByTestId('offline-pending-badge')).toBeNull()

    await queueOperation('crm', 'crm.lead.noter', { lead: 7, body: 'x' }, { target: 7 })
    await waitFor(() => {
      expect(screen.getByTestId('ligne-7')
        .querySelector('[data-testid="offline-pending-badge"]')).not.toBeNull()
    })
    // …et pas sur la ligne voisine.
    expect(screen.getByTestId('ligne-9')
      .querySelector('[data-testid="offline-pending-badge"]')).toBeNull()

    await queueOperation('crm', 'crm.lead.tag', { lead: 7, tag: 'chaud' }, { target: 7 })
    await waitFor(() => {
      expect(screen.getByTestId('ligne-7')
        .querySelector('[data-testid="offline-pending-badge"]'))
        .toHaveAttribute('data-offline-pending', '2')
    })
  })

  it('agrège aussi la file TERRAIN quand l’écran nomme sa clé de corps', async () => {
    fieldOutbox.pending.mockResolvedValue([
      { client_op_id: 'a', op_type: 'chantier.cocher_checklist', payload: { chantier: 9 } },
      { client_op_id: 'b', op_type: 'chantier.cocher_checklist', payload: { chantier: 9 } },
    ])
    render(<Liste champ="chantier" />)
    await waitFor(() => {
      expect(screen.getByTestId('ligne-9')
        .querySelector('[data-testid="offline-pending-badge"]'))
        .toHaveAttribute('data-offline-pending', '2')
    })
  })
})
