import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import crmApi from '../../../api/crmApi'
import { toast } from '../../../ui'
import { useLeadDraft } from './useLeadDraft'

// LW42 — `changeStage` : messages d'erreur fidèles. Avant ce fix, TOUT 400
// affichait le même toast fixe « Retour d'étape non autorisé » (un lead perdu
// verrouillé recevait le mauvais message) et toute autre panne (réseau,
// serveur, 400 sans detail) restait totalement silencieuse (clic muet en
// offline). Le fix surface `err.response.data.detail` quand présent, sinon un
// toast générique — jamais de silence.

vi.mock('../../../api/crmApi', () => ({
  default: {
    updateLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))
vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, error: vi.fn(), success: vi.fn() } }
})

const LEAD_A = { id: 1, nom: 'Ali', stage: 'NEW', is_archived: false, date_modification: 'a' }

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { vi.clearAllMocks() })

describe('LW42 — changeStage messages d’erreur fidèles', () => {
  it('400 avec `detail` serveur → toast au TEXTE SERVEUR (pas le générique fixe)', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Lead perdu — motif requis avant tout changement.' } },
    })
    const { result } = renderHook(() => useLeadDraft(LEAD_A, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('CONTACTED') })
    expect(toast.error).toHaveBeenCalledWith('Lead perdu — motif requis avant tout changement.')
  })

  it('erreur réseau (pas de réponse) → toast GÉNÉRIQUE, jamais un clic muet', async () => {
    crmApi.updateLead.mockRejectedValueOnce(new Error('Network Error'))
    const { result } = renderHook(() => useLeadDraft(LEAD_A, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('CONTACTED') })
    expect(toast.error).toHaveBeenCalledWith("Échec du changement d'étape — réessayez.")
  })

  it('400 SANS `detail` → toast générique aussi (jamais silencieux)', async () => {
    crmApi.updateLead.mockRejectedValueOnce({ response: { status: 400, data: {} } })
    const { result } = renderHook(() => useLeadDraft(LEAD_A, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('CONTACTED') })
    expect(toast.error).toHaveBeenCalledWith("Échec du changement d'étape — réessayez.")
  })
})

// ORDRE FONDATEUR 2026-08-01 (reculer d'étape) — le MOTEUR transporte la
// réponse jusqu'au corps du PATCH, il ne la produit pas : il n'a pas d'UI, donc
// ne pose aucune question, et le marqueur est OMIS quand il est faux.
describe('changeStage — transport du marqueur confirme_recul', () => {
  it('une avancée reste un PATCH nu : { stage } seulement', async () => {
    const { result } = renderHook(() => useLeadDraft(LEAD_A, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('CONTACTED') })
    expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED' })
  })

  it('une réponse « oui » (confirmeRecul) part dans le corps du PATCH', async () => {
    const { result } = renderHook(() => useLeadDraft(LEAD_A, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('CONTACTED', { confirmeRecul: true }) })
    expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED', confirme_recul: true })
  })

  it('un confirmeRecul faux est omis du corps, et le moteur ne pose jamais de question', async () => {
    const confirmNatif = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { result } = renderHook(() => useLeadDraft(LEAD_A, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('CONTACTED', { confirmeRecul: false }) })
    expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED' })
    expect(confirmNatif).not.toHaveBeenCalled()
    confirmNatif.mockRestore()
  })
})
