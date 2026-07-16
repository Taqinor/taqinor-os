import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* VX31 — boîte de réception SAV : sur grand viewport (≥1280px), `TicketDetail`
   rend un panneau latéral PERSISTANT (aside) à côté de la liste au lieu du
   `Sheet` plein-tiroir ; sous ce seuil, le `Sheet` reste le fallback mobile/
   tablette inchangé. On simule `matchMedia` aux deux points de rupture, comme
   `ResponsiveDialog.test.jsx` (M158) le fait déjà pour le même mécanisme. */

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))

vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

// Stub matchMedia déterministe : `desktop=true` fait matcher la requête
// `min-width: 1280px` (chemin panneau latéral) ; `desktop=false` la fait
// échouer (chemin Sheet plein-tiroir).
function mockMatchMedia(desktop) {
  window.matchMedia = (query) => ({
    matches: desktop,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })
}

function makeStore() {
  return configureStore({
    reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role: 'admin', permissions: [] }) => state,
    },
  })
}

const baseTicket = {
  id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null,
}

function renderDetail() {
  const store = makeStore()
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
