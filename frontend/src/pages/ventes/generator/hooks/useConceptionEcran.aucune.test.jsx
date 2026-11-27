// Nouveau fichier car : aucun module de test ne couvre le hook useConceptionEcran seul (les autres le montent via l'écran devis).
// Lead neuf : le serveur répond 200 `exemple_aucune` (contrat conception_lead.json) — rien de rangé, aperçu sur les seules colonnes.
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

import { exempleContrat } from '../../../../test/fixtures/contractSamples'

vi.mock('../../../../api/ventesApi', () => ({
  default: { getConceptionLead: vi.fn(), apercuConception: vi.fn(() => new Promise(() => {})) },
}))

import ventesApi from '../../../../api/ventesApi'
import { useConceptionEcran } from './useConceptionEcran'

describe('useConceptionEcran — lead sans conception (200 « aucune »)', () => {
  it('rien de rangé (servie nulle), aperçu demandé sur les seules colonnes du lead, un seul GET', async () => {
    ventesApi.getConceptionLead.mockResolvedValue({ data: exempleContrat('ventes', 'conception_lead', 'exemple_aucune') })
    const { result } = renderHook(() => useConceptionEcran({ leadId: 7, corps: null }))
    await waitFor(() => expect(ventesApi.apercuConception).toHaveBeenCalled())
    expect(ventesApi.getConceptionLead).toHaveBeenCalledTimes(1)
    expect(result.current.servie).toBeNull()
    expect(ventesApi.apercuConception.mock.calls[0][0]).toMatchObject({ lead: 7, entrees: {}, imposes: {} })
  })
})
