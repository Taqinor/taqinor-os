import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import crmApi from '../../../api/crmApi'
import { toast } from '../../../ui'
import { useLeadDraft } from './useLeadDraft'

// ALEA18 — l'autosave ne réémet JAMAIS une charge déjà refusée en 400 tant que
// le brouillon n'a pas changé (constaté en direct le 07/10/2026 : 15 PATCH 400
// identiques en ~20 s, toast répété) ; un enregistrement réussi efface l'erreur
// périmée sous les champs écrits. Serveur factice : il REFUSE (400) toute
// valeur de GPS à plus de 6 décimales et ACCEPTE le reste — on compte les
// requêtes reçues, jamais un espion sur `flush`.

vi.mock('../../../api/crmApi', () => ({
  default: { updateLead: vi.fn() },
}))
vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, error: vi.fn(), success: vi.fn() } }
})

const LEAD = { id: 1, nom: 'Ali', stage: 'NEW', is_archived: false, date_modification: 'a', gps_lat: null }

function serveurFactice() {
  crmApi.updateLead.mockImplementation((id, payload) => {
    const v = String(payload.gps_lat ?? '')
    if (v.split('.')[1]?.length > 6) {
      return Promise.reject({
        response: { status: 400, data: { gps_lat: ['Format invalide'] } },
      })
    }
    return Promise.resolve({ data: { id, gps_lat: payload.gps_lat, date_modification: 'b' } })
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  sessionStorage.clear()
  vi.clearAllMocks()
  serveurFactice()
})
afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('ALEA18 — autosave et refus 400', () => {
  it('une charge refusée n’est envoyée qu’une fois, avec un seul toast', async () => {
    const onFieldErrors = vi.fn()
    const { result } = renderHook(() => useLeadDraft(LEAD, {
      mode: 'edit', currentUserId: 42, onFieldErrors,
    }))
    act(() => { result.current.setField('gps_lat', '33.5731104') })
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(crmApi.updateLead).toHaveBeenCalledTimes(1)
    expect(toast.error).toHaveBeenCalledTimes(1)
    expect(result.current.saveState).toBe('error')
    expect(onFieldErrors).toHaveBeenCalledTimes(1)
    // 15 s de plus sans toucher : toujours une seule requête.
    await act(async () => { await vi.advanceTimersByTimeAsync(15000) })
    expect(crmApi.updateLead).toHaveBeenCalledTimes(1)
    expect(toast.error).toHaveBeenCalledTimes(1)
  })

  it('corriger le champ renvoie une charge différente ; le succès efface l’erreur du champ', async () => {
    const onFieldsSaved = vi.fn()
    const { result } = renderHook(() => useLeadDraft(LEAD, {
      mode: 'edit', currentUserId: 42, onFieldsSaved,
    }))
    act(() => { result.current.setField('gps_lat', '33.5731104') })
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(crmApi.updateLead).toHaveBeenCalledTimes(1)
    expect(onFieldsSaved).not.toHaveBeenCalled()

    act(() => { result.current.setField('gps_lat', '33.573110') })
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(crmApi.updateLead).toHaveBeenCalledTimes(2)
    expect(result.current.saveState).toBe('saved')
    expect(onFieldsSaved).toHaveBeenCalledWith(['gps_lat'])
  })

  it('« Réessayer » (flush forcé) reste possible sur une charge refusée', async () => {
    const { result } = renderHook(() => useLeadDraft(LEAD, { mode: 'edit', currentUserId: 42 }))
    act(() => { result.current.setField('gps_lat', '33.5731104') })
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(crmApi.updateLead).toHaveBeenCalledTimes(1)
    await act(async () => { await result.current.retry() })
    expect(crmApi.updateLead).toHaveBeenCalledTimes(2)
  })
})
