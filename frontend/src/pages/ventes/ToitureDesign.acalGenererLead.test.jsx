import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* ACAL97 (C-ACAL-102) — « Générer le devis » de l'atelier LEAD ne re-poste
   plus le layout BRUT après from-layout : from-layout range DÉJÀ la conception
   enrichie côté serveur (`_pans_geometry`…) ; l'ancienne étape 2 « persistance
   idempotente best-effort » (POST /ventes/devis/<id>/layout/) l'écrasait.
   Seul le client HTTP est simulé, comme dans les autres tests ToitureDesign. */

vi.mock('../../hooks/useHasPermission', () => ({ useHasPermission: () => false }))

import { initRoofToolPro8, rendreLead, reinitialiserBoot, simulerApiLead }
  from '../../test/toitureDesignHarness'
import api from '../../api/axios'

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserBoot()
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ToitureDesign — mode lead : Générer (ACAL97)', () => {
  it('Générer (mode lead) n’appelle pas /ventes/devis/<id>/layout/', async () => {
    simulerApiLead(api)
    api.post.mockImplementation((url) => {
      if (url === '/ventes/devis/from-layout/') {
        return Promise.resolve({ status: 201, data: { id: 501, reference: 'DEV-ACAL97-1' } })
      }
      return Promise.resolve({ data: {} })
    })

    rendreLead(88)
    await waitFor(() => expect(initRoofToolPro8).toHaveBeenCalled())
    await userEvent.click(await screen.findByRole('button',
      { name: /Générer le devis & envoyer au client/ }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/ventes/devis/from-layout/', expect.objectContaining({ lead: '88' })))
    expect((await screen.findAllByText(/DEV-ACAL97-1/)).length).toBeGreaterThan(0)
    const urls = api.post.mock.calls.map(([url]) => url)
    expect(urls).not.toContain('/ventes/devis/501/layout/')
    expect(urls.filter((u) => /\/ventes\/devis\/\d+\/layout\/$/.test(u))).toEqual([])
  })
})
