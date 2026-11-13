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
// AERR119 — le toast « Annuler » est capturé (son `onUndo` est rejoué).
const undoToast = vi.hoisted(() => ({ fn: vi.fn() }))
vi.mock('../../../lib/toast', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toastWithUndo: undoToast.fn }
})
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

  it('ACVI9 — 409 sur `parc_raison` → toast au TEXTE SERVEUR', async () => {
    crmApi.updateLead.mockRejectedValueOnce({
      response: { status: 409, data: { parc_raison: ['Raison de mise au Froid obligatoire.'] } },
    })
    const { result } = renderHook(() => useLeadDraft({ lead: LEAD_A, mode: 'edit' }))
    await act(async () => { await result.current.changeStage('COLD') })
    expect(toast.error).toHaveBeenCalledWith('Raison de mise au Froid obligatoire.')
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

// AERR119 (D-AERR-2) — une avancée par les touches 1-4 / le menu d'étape offre
// « Annuler » comme le kanban : toast nommé, PATCH inverse avec `undo`.
describe('changeStage — Annuler comme le kanban (AERR119)', () => {
  const AHMED = { id: 1, prenom: 'Ahmed', nom: 'Benali', stage: 'CONTACTED', date_modification: 'a' }

  it('avancée : toast nommé + Annuler qui renvoie l\'étape d\'origine avec undo', async () => {
    crmApi.updateLead
      .mockResolvedValueOnce({ data: { ...AHMED, stage: 'QUOTE_SENT' } })
      .mockResolvedValueOnce({ data: { ...AHMED, stage: 'CONTACTED' } })
    const { result } = renderHook(() => useLeadDraft(AHMED, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('QUOTE_SENT') })
    expect(crmApi.updateLead).toHaveBeenNthCalledWith(1, 1, { stage: 'QUOTE_SENT' })
    expect(undoToast.fn).toHaveBeenCalledTimes(1)
    const { message, onUndo, onCommit } = undoToast.fn.mock.calls[0][0]
    expect(message).toBe('Lead « Ahmed Benali » → Devis envoyé')
    expect(onCommit).toBeUndefined()
    await act(async () => { await onUndo() })
    expect(crmApi.updateLead).toHaveBeenNthCalledWith(2, 1, { stage: 'CONTACTED', undo: true })
    expect(result.current.state.server.stage).toBe('CONTACTED')
  })

  it('recul confirmé ou Froid avec raison : pas d\'« Annuler »', async () => {
    const { result } = renderHook(() => useLeadDraft(AHMED, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { await result.current.changeStage('NEW', { confirmeRecul: true }) })
    await act(async () => { await result.current.changeStage('COLD', { parcRaison: 'pas_interesse' }) })
    expect(undoToast.fn).not.toHaveBeenCalled()
  })
})
