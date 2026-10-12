// ENF28 (ENF19) — banc d'essai partagé des tests de `TicketDetail` (fiche
// ticket SAV). Chaque fichier de test recopiait les mêmes mocks neutres et le
// même rendu (store redux minimal) ; un seul exemplaire ici. Utilisé dans les
// fabriques `vi.mock` par import dynamique, ex. :
//   vi.mock('../../api/savApi', async () =>
//     (await import('./__tests__/ticketDetailTestKit')).savApiDetailMock({ ... }))
import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/** savApi : toutes les lectures faites au montage de TicketDetail, neutres. */
export function savApiDetailMock(extra = {}) {
  return {
    default: {
      getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
      getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
      getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
      // XSAV12/21/27/28, ZSAV8/9 — TicketAdvancedPanel (montée dans TicketDetail).
      getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
      getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
      getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
      getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
      // WR11/FG82 — TicketChecklistPanel (montée dans TicketDetail).
      getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
      getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
      ...extra,
    },
  }
}

/** ticketsSlice réel, sauf `updateTicket` qui ne fait rien (unwrap résolu). */
export async function ticketsSliceNoopMock(importOriginal) {
  const actual = await importOriginal()
  return {
    ...actual,
    updateTicket: () => {
      const action = { type: 'sav/updateTicket/noop' }
      action.unwrap = () => Promise.resolve({})
      return action
    },
  }
}

/** api (axios direct) : tout GET rend une liste vide. */
export function axiosVideMock() {
  return { default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }
}

/** installationsApi : aucune intervention liée. */
export function installationsApiVideMock() {
  return { default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) } }
}

/** Store redux minimal (admin, aucun ticket en mémoire). */
export function makeTicketStore() {
  return configureStore({
    reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role: 'admin', permissions: [] }) => state,
    },
  })
}

/** Rend `TicketDetail` dans son store (et un routeur mémoire si `routeur`). */
export function renderTicketDetail(TicketDetail, ticket, opts = {}, { routeur = true } = {}) {
  const fiche = <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} {...opts} />
  return render(
    <Provider store={makeTicketStore()}>
      {routeur ? <MemoryRouter>{fiche}</MemoryRouter> : fiche}
    </Provider>,
  )
}
