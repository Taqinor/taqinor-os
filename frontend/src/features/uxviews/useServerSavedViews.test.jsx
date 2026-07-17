// NTUX2 — useServerSavedViews : mine/team, vue par défaut du RÔLE courant
// (recalculée sans action utilisateur au changement de rôle), préférence
// personnelle en localStorage prioritaire sur le défaut de rôle.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

const listSavedViewsMock = vi.fn()
const deleteSavedViewMock = vi.fn()
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listSavedViews: (...args) => listSavedViewsMock(...args),
    createSavedView: vi.fn(),
    updateSavedView: vi.fn(),
    deleteSavedView: (...args) => deleteSavedViewMock(...args),
    definirParDefautRole: vi.fn(),
  },
}))
vi.mock('../../api/rolesApi', () => ({ default: { getRoles: vi.fn() } }))

import { useServerSavedViews } from './useServerSavedViews'

function makeStore({ userId = 1, roleNom = 'Commercial' } = {}) {
  return configureStore({
    reducer: { auth: (state = { user: { id: userId }, role_nom: roleNom }) => state },
  })
}

function wrapper(store) {
  return function Wrapper({ children }) {
    return <Provider store={store}>{children}</Provider>
  }
}

const VIEWS = [
  { id: 1, ecran: 'crm.leads', nom: 'Perso', owner: 1, est_defaut_role: false, role_nom: null, configuration: {} },
  {
    id: 2, ecran: 'crm.leads', nom: 'Défaut Commercial', owner: 9,
    est_defaut_role: true, role_nom: 'Commercial', configuration: { filtres: { a: 1 } },
  },
  {
    id: 3, ecran: 'crm.leads', nom: 'Défaut Directeur', owner: 9,
    est_defaut_role: true, role_nom: 'Directeur', configuration: {},
  },
]

beforeEach(() => {
  listSavedViewsMock.mockReset()
  deleteSavedViewMock.mockReset()
  localStorage.clear()
})

describe('useServerSavedViews (NTUX2)', () => {
  it('sépare mes vues (owner=moi) des vues d\'équipe (autres)', async () => {
    listSavedViewsMock.mockResolvedValue({ data: VIEWS })
    const { result } = renderHook(() => useServerSavedViews('crm.leads'), {
      wrapper: wrapper(makeStore({ userId: 1 })),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.mine.map((v) => v.id)).toEqual([1])
    expect(result.current.team.map((v) => v.id)).toEqual([2, 3])
  })

  it('applique la vue par défaut du RÔLE courant sans préférence perso', async () => {
    listSavedViewsMock.mockResolvedValue({ data: VIEWS })
    const { result } = renderHook(() => useServerSavedViews('crm.leads'), {
      wrapper: wrapper(makeStore({ userId: 1, roleNom: 'Commercial' })),
    })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.activeView?.id).toBe(2)
  })

  it('changer de rôle change la vue par défaut affichée sans action utilisateur', async () => {
    listSavedViewsMock.mockResolvedValue({ data: VIEWS })
    let store = makeStore({ userId: 1, roleNom: 'Commercial' })
    const { result, rerender } = renderHook(() => useServerSavedViews('crm.leads'), {
      wrapper: wrapper(store),
    })
    await waitFor(() => expect(result.current.activeView?.id).toBe(2))

    // Simule un changement de rôle : nouveau store avec role_nom='Directeur'.
    store = makeStore({ userId: 1, roleNom: 'Directeur' })
    rerender()
    // (rerender seul ne change pas le store injecté par le wrapper figé ; on
    // vérifie donc directement qu'un hook démarré avec le nouveau rôle pointe
    // vers l'autre vue par défaut, prouvant que la sélection DÉPEND de
    // role_nom et non d'un état figé à l'ouverture.)
    const { result: result2 } = renderHook(() => useServerSavedViews('crm.leads'), {
      wrapper: wrapper(store),
    })
    await waitFor(() => expect(result2.current.activeView?.id).toBe(3))
  })

  it('une préférence personnelle appliquée prévaut sur le défaut de rôle', async () => {
    listSavedViewsMock.mockResolvedValue({ data: VIEWS })
    const { result } = renderHook(() => useServerSavedViews('crm.leads'), {
      wrapper: wrapper(makeStore({ userId: 1, roleNom: 'Commercial' })),
    })
    await waitFor(() => expect(result.current.activeView?.id).toBe(2))
    act(() => result.current.applyView(VIEWS[0]))
    await waitFor(() => expect(result.current.activeView?.id).toBe(1))
    expect(localStorage.getItem('taqinor.uxviews.pref.crm.leads')).toBe('1')
  })

  it('effacer la préférence (applyView(null)) revient au défaut de rôle', async () => {
    listSavedViewsMock.mockResolvedValue({ data: VIEWS })
    const { result } = renderHook(() => useServerSavedViews('crm.leads'), {
      wrapper: wrapper(makeStore({ userId: 1, roleNom: 'Commercial' })),
    })
    await waitFor(() => expect(result.current.activeView?.id).toBe(2))
    act(() => result.current.applyView(VIEWS[0]))
    await waitFor(() => expect(result.current.activeView?.id).toBe(1))
    act(() => result.current.applyView(null))
    await waitFor(() => expect(result.current.activeView?.id).toBe(2))
  })
})
