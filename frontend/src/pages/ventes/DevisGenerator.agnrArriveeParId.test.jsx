// AGNR19 — le lead et le client d'ARRIVÉE sont résolus PAR LEUR ID
// (`crmApi.getLead(id)`, `getClient(id)`), jamais cherchés dans une page de
// liste : `?lead=<plus ancien>` applique ce lead (factures comprises),
// `?client=<plus ancien>` le résout, un id inexistant est DIT.
//
// Run : npx vitest run src/pages/ventes/DevisGenerator.agnrArriveeParId.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, waitFor } from '@testing-library/react'

import { DATE_FIGEE, monter, attendreStable } from './DevisGeneratorGoldenHarnais'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

// 60 enregistrements ; la LISTE ne sert que les 50 plus récents (page 1 d'un
// serveur qui ne pagine pas plus loin), le détail par id sert tout le monde.
const LEADS = Array.from({ length: 60 }, (_, k) => ({
  id: 60 - k, nom: `Lead${60 - k}`, prenom: '', societe: '',
  facture_hiver: 60 - k === 1 ? '1800' : null, ete_differente: false,
}))
const CLIENTS = Array.from({ length: 60 }, (_, k) => ({
  id: 60 - k, nom: `Client${60 - k}`, adresse: `Adresse ${60 - k}`, telephone: '',
}))
const parId = (items) => (id) => {
  const trouve = items.find((x) => String(x.id) === String(id))
  return trouve ? Promise.resolve({ data: trouve })
    : Promise.reject(Object.assign(new Error('404'), { response: { status: 404 } }))
}
const serveur = ({ crmApi }) => {
  crmApi.getLeads.mockResolvedValue({ data: LEADS.slice(0, 50) })
  crmApi.getClients.mockResolvedValue({ data: CLIENTS.slice(0, 50) })
  crmApi.getLead.mockImplementation(parId(LEADS))
  crmApi.getClient.mockImplementation(parId(CLIENTS))
}

cycleEcran({ date: DATE_FIGEE })

describe('AGNR19 — lead et client d’arrivée résolus par leur id', () => {
  it('?lead=<plus ancien> : lead affiché et factures appliquées', async () => {
    const vue = await monter('/ventes/devis/nouveau?lead=1', { avant: serveur })
    await waitFor(() => expect(vue.crmApi.getLead).toHaveBeenCalledWith('1'))
    await attendreStable(vue.container, act)
    expect(document.getElementById('gen-lead')?.textContent).toContain('Lead1')
    expect(document.getElementById('gen-hiver')?.value).toBe('1800')
  }, 60000)

  it('?lead=<id inexistant> : « Lead introuvable » au lieu d’un écran muet', async () => {
    const vue = await monter('/ventes/devis/nouveau?lead=999', { avant: serveur })
    await waitFor(() => expect(vue.crmApi.getLead).toHaveBeenCalledWith('999'))
    await attendreStable(vue.container, act)
    expect(document.body.textContent).toMatch(/Lead introuvable \(n° 999\)/)
  }, 60000)

  it('?client=<plus ancien> : client résolu (adresse affichée)', async () => {
    const vue = await monter('/ventes/devis/nouveau?client=1', { avant: serveur })
    await waitFor(() => expect(vue.crmApi.getClient).toHaveBeenCalledWith('1'))
    await attendreStable(vue.container, act)
    expect(document.getElementById('gen-adresse')?.value).toBe('Adresse 1')
  }, 60000)
})
