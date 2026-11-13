import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'

/* VX31 — boîte de réception SAV : sur grand viewport (≥1280px), `TicketDetail`
   rend un panneau latéral PERSISTANT (aside) à côté de la liste au lieu du
   `Sheet` plein-tiroir ; sous ce seuil, le `Sheet` reste le fallback mobile/
   tablette inchangé. On simule `matchMedia` aux deux points de rupture, comme
   `ResponsiveDialog.test.jsx` (M158) le fait déjà pour le même mécanisme. */

vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailTestKit')).savApiDetailMock({
  // AERR25 — le PATCH de « Mettre à jour » (thunk updateTicket réel).
  updateTicket: vi.fn((id, data) => Promise.resolve({ data: { id, ...data } })),
}))

vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailTestKit')).axiosVideMock())

vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailTestKit')).installationsApiVideMock())

import api from '../../api/axios'
import savApi from '../../api/savApi'
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

function renderDetail(auth) {
  const store = makeTicketStore(auth)
  return render(
    <Provider store={store}>
      <TicketDetail ticket={baseTicket} onClose={() => {}} onSaved={() => {}} />
    </Provider>,
  )
}

describe('TicketDetail — ERR-SAV-TECH-USERS-403 liste des utilisateurs', () => {
  const appelsUsers = () => api.get.mock.calls.filter(([url]) => url === '/users/')

  it("n'appelle pas GET /users/ pour un Technicien (permission servie absente)", async () => {
    mockMatchMedia(true)
    renderDetail({ role: 'normal', role_nom: 'Technicien', permissions: ['sav_voir'] })
    await screen.findByText('SAV-1', { exact: false })
    expect(appelsUsers()).toHaveLength(0)
  })

  it('appelle GET /users/ quand users_gerer est servie', async () => {
    mockMatchMedia(true)
    renderDetail({ role: 'normal', permissions: ['users_gerer'] })
    await screen.findByText('SAV-1', { exact: false })
    expect(appelsUsers()).toHaveLength(1)
  })

  it('appelle GET /users/ pour le palier admin', async () => {
    mockMatchMedia(true)
    renderDetail({ role: 'admin', permissions: [] })
    await screen.findByText('SAV-1', { exact: false })
    expect(appelsUsers()).toHaveLength(1)
  })
})

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

describe('TicketDetail — AERR25 la fiche suit le ticket sélectionné', () => {
  it('rerender A → B puis Mettre à jour : PATCH de B avec les champs de B', async () => {
    mockMatchMedia(true)
    const ticketA = {
      ...baseTicket, id: 1, reference: 'SAV-1', priorite: 'urgente', description: 'Onduleur HS',
    }
    const ticketB = {
      ...baseTicket, id: 2, reference: 'SAV-2', priorite: 'normale', description: 'Panneau fissuré',
    }
    const store = makeTicketStore()
    const fiche = (t) => (
      <Provider store={store}>
        <TicketDetail ticket={t} onClose={() => {}} onSaved={() => {}} />
      </Provider>
    )
    const { rerender } = render(fiche(ticketA))
    await screen.findByText('SAV-1', { exact: false })
    rerender(fiche(ticketB))
    await screen.findByText('SAV-2', { exact: false })
    expect(document.querySelector('aside').getAttribute('aria-label')).toMatch(/SAV-2/)
    fireEvent.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    await waitFor(() => expect(savApi.updateTicket).toHaveBeenCalled())
    const [id, data] = savApi.updateTicket.mock.calls[0]
    expect(id).toBe(2)
    expect(data.priorite).toBe('normale')
    expect(data.description).toBe('Panneau fissuré')
  })
})
