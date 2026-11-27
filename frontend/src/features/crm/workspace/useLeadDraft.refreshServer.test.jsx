// ACAL1243 (suite) — Nouveau fichier car : aucun module de test ne couvre
// `refreshServer` avec le VRAI intercepteur axios. Après un envoi de devis réussi,
// le rafraîchissement de la fiche (GET) peut expirer : le devis EST parti, le
// toast global « La connexion a expiré » serait faux. Le GET est donc silencieux
// (`suppressErrorToast`) ; ici l'intercepteur réel tourne, seul l'adaptateur réseau est factice.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { AxiosError } from 'axios'
import api from '../../../api/axios'
import { toastError } from '../../../lib/toast'
import { useLeadDraft } from './useLeadDraft'

vi.mock('../../../lib/toast', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toastError: vi.fn() }
})

const LEAD = { id: 7, nom: 'Ali', stage: 'NEW', is_archived: false, date_modification: 'a' }

describe('ACAL1243 — refreshServer après un envoi', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear() })

  it('un rafraîchissement qui expire (ECONNABORTED) ne lève aucun toast et ne casse rien', async () => {
    const requetes = []
    api.defaults.adapter = (config) => {
      requetes.push(config)
      return Promise.reject(new AxiosError('timeout', 'ECONNABORTED', config))
    }
    const { result } = renderHook(() => useLeadDraft(LEAD, { mode: 'edit' }))
    await act(async () => { await result.current.refreshServer() })
    expect(requetes.some((c) => String(c.url).includes('/crm/leads/7/'))).toBe(true)
    expect(toastError).not.toHaveBeenCalled()
  })
})
