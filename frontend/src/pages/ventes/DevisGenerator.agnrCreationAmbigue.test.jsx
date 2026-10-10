// AGNR40 (C-AGNR-028) — la création d'un devis (`POST /ventes/devis/atomic/`)
// part avec une `Idempotency-Key` PAR SESSION de création : un 2ᵉ clic après
// une coupure réseau renvoie la MÊME clé (le serveur rejoue alors le premier
// devis au lieu d'en créer un second). Un échec à issue inconnue (coupure,
// délai, 5xx sans corps) est DIT comme tel — jamais « vérifiez les champs ».
//
// Harnais du golden (seules les quatre API sont mockées, jamais l'écran).
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, fireEvent, waitFor } from '@testing-library/react'

import { DATE_FIGEE, LEAD, monter, attendreStable, autoRemplirAvecPanneaux } from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

const COUPURE = Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })
const MESSAGE = /connexion a été interrompue — vérifiez la liste des devis avant de recréer/

cycleEcran({ date: DATE_FIGEE })

const cliquerCreer = async () => {
  const b = [...document.querySelectorAll('button')].find((x) => /Créer le devis/.test(x.textContent || ''))
  expect(b, 'bouton « Créer le devis »').toBeTruthy()
  await act(async () => { fireEvent.click(b) })
}

describe('AGNR40 — création à issue inconnue', () => {
  it('coupure : message dédié, puis 2ᵉ clic avec la MÊME Idempotency-Key', async () => {
    const vue = await monter(`/ventes/devis/nouveau?lead=${LEAD.id}`, {
      avant: ({ ventesApi }) => {
        ventesApi.composerDevis.mockResolvedValue({ data: exempleContrat('ventes', 'devis_composition', 'exemple') })
        ventesApi.createDevisAtomic
          .mockRejectedValueOnce(COUPURE)
          .mockResolvedValue({ data: { id: 900, reference: 'DEV-202610-0900', statut: 'brouillon' } })
      },
    })
    await attendreStable(vue.container, act)
    await autoRemplirAvecPanneaux('8')
    await waitFor(() => expect(vue.ventesApi.composerDevis).toHaveBeenCalled())
    await attendreStable(vue.container, act)

    await cliquerCreer()
    await waitFor(() => expect(vue.ventesApi.createDevisAtomic).toHaveBeenCalledTimes(1), { timeout: 5000 })
    await attendreStable(vue.container, act, { stables: 5 })
    expect(vue.container.textContent).toMatch(MESSAGE)
    expect(vue.container.textContent).not.toMatch(/vérifiez les champs et réessayez/)

    await cliquerCreer()
    await waitFor(() => expect(vue.ventesApi.createDevisAtomic).toHaveBeenCalledTimes(2), { timeout: 5000 })
    const [, opts1] = vue.ventesApi.createDevisAtomic.mock.calls[0]
    const [, opts2] = vue.ventesApi.createDevisAtomic.mock.calls[1]
    expect(typeof opts1?.idempotencyKey).toBe('string')
    expect(opts1.idempotencyKey.length).toBeGreaterThan(8)
    expect(opts2?.idempotencyKey).toBe(opts1.idempotencyKey)
  }, 60000)
})
