import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'

/* VX31 — boîte de réception SAV : sur grand viewport (≥1280px), `TicketDetail`
   rend un panneau latéral PERSISTANT (aside) à côté de la liste au lieu du
   `Sheet` plein-tiroir ; sous ce seuil, le `Sheet` reste le fallback mobile/
   tablette inchangé. On simule `matchMedia` aux deux points de rupture, comme
   `ResponsiveDialog.test.jsx` (M158) le fait déjà pour le même mécanisme. */

vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailTestKit')).savApiDetailMock())

vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailTestKit')).axiosVideMock())

vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailTestKit')).installationsApiVideMock())

import { TicketDetail } from './TicketsPage'
import { makeTicketStore } from './__tests__/ticketDetailTestKit'
import { mockMatchMedia } from '../../test/matchMedia'

afterEach(() => { cleanup(); vi.clearAllMocks() })

// Stub matchMedia déterministe : `desktop=true` fait matcher la requête
// `min-width: 1280px` (chemin panneau latéral) ; `desktop=false` la fait
// échouer (chemin Sheet plein-tiroir).

const baseTicket = {
  id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null,
}

function renderDetail() {
  const store = makeTicketStore()
  return render(
    <Provider store={store}>
      <TicketDetail ticket={baseTicket} onClose={() => {}} onSaved={() => {}} />
    </Provider>,
  )
}

describe('TicketDetail — VX31 split-view desktop vs Sheet mobile/tablette', () => {
  it('sur grand viewport (≥1280px) rend un panneau latéral persistant (aside), jamais un tiroir', async () => {
    mockMatchMedia(true)
    renderDetail()
    await screen.findByText('SAV-1', { exact: false })
    // Panneau latéral : un <aside> nommé, pas de rôle dialog (aucun tiroir/portail modal).
    const aside = document.querySelector('aside')
    expect(aside).toBeTruthy()
    expect(aside.getAttribute('aria-label')).toMatch(/SAV-1/)
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })

  it('sous 1280px retombe sur le Sheet plein-tiroir (fallback inchangé)', async () => {
    mockMatchMedia(false)
    renderDetail()
    await screen.findByText('SAV-1', { exact: false })
    // Tiroir Sheet : rôle dialog rendu via portail Radix ; aucun <aside>.
    expect(document.querySelector('[role="dialog"]')).toBeTruthy()
    expect(document.querySelector('aside')).toBeNull()
  })
})
