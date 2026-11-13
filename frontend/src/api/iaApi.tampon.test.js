import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

/* NOUVEAU FICHIER DE TEST : `iaApi.js` n'a aucun test d'intercepteur (les autres
   tests de l'assistant mockent tout le client). Ici le VRAI client tourne sur un
   adaptateur axios simulé, pour prouver que chaque appel de l'assistant — succès
   ou échec — est noté dans le tampon de diagnostic (COP-F7), sans corps. */

vi.mock('../lib/tamponDiagnostic', () => ({ noterRequete: vi.fn() }))
vi.mock('../lib/journalProblemes', () => ({ signalerErreurRequete: vi.fn() }))
vi.mock('../lib/toast', () => ({ toastError: vi.fn() }))

import { noterRequete } from '../lib/tamponDiagnostic'

async function chargerClient(adaptateur) {
  // `axios.create` hérite des défauts au moment de la création : l'adaptateur
  // simulé doit être posé AVANT l'import du client.
  axios.defaults.adapter = adaptateur
  vi.resetModules()
  return (await import('./iaApi')).default
}

beforeEach(() => { vi.clearAllMocks() })

describe('iaApi — tampon de diagnostic (COP-F7)', () => {
  it('un appel réussi est noté : méthode, route, statut, durée, request_id — jamais de corps', async () => {
    const iaApi = await chargerClient((config) => Promise.resolve({
      data: { answer: 'secret client' }, status: 200, statusText: 'OK',
      headers: { 'x-request-id': '0123456789abcdef0123456789abcdef' }, config,
    }))
    await iaApi.queryAgent('Quel est le téléphone de M. Benali ?', { ecran: '/crm' })
    expect(noterRequete).toHaveBeenCalledTimes(1)
    const note = noterRequete.mock.calls[0][0]
    expect(note).toMatchObject({
      methode: 'POST', url: '/api/fastapi/sql-agent/query', statut: 200,
      requestId: '0123456789abcdef0123456789abcdef',
    })
    expect(typeof note.dureeMs).toBe('number')
    expect(JSON.stringify(note)).not.toMatch(/Benali|secret client/)
  })

  it('un échec (5xx) est noté, et la panne de l\'assistant se voit', async () => {
    const iaApi = await chargerClient((config) => Promise.reject(new axios.AxiosError(
      'boom', 'ERR_BAD_RESPONSE', config, null,
      { status: 502, data: {}, headers: {}, config },
    )))
    await expect(iaApi.confirmAction('jeton')).rejects.toBeTruthy()
    expect(noterRequete).toHaveBeenCalledWith(expect.objectContaining({
      methode: 'POST', url: '/api/fastapi/sql-agent/confirm', statut: 502, code: 'ERR_BAD_RESPONSE',
    }))
  })

  it('une coupure réseau (aucune réponse) est notée avec le statut 0', async () => {
    const iaApi = await chargerClient((config) => Promise.reject(
      new axios.AxiosError('Network Error', 'ERR_NETWORK', config)))
    await expect(iaApi.getChatHistory()).rejects.toBeTruthy()
    expect(noterRequete).toHaveBeenCalledWith(expect.objectContaining({ statut: 0, code: 'ERR_NETWORK' }))
  })

  it('les lectures Django de l\'assistant (touche, file) sont notées aussi', async () => {
    const iaApi = await chargerClient((config) => Promise.resolve({ data: {}, status: 200, statusText: 'OK', headers: {}, config }))
    await iaApi.getToucheAssistant(412)
    await iaApi.getFileTouchesAssistant()
    expect(noterRequete.mock.calls.map((c) => c[0].url)).toEqual([
      '/api/django/crm/assistant/touches/412/', '/api/django/crm/assistant/a-relancer/',
    ])
  })

  it('l\'OCR (hors assistant) n\'est pas noté', async () => {
    const iaApi = await chargerClient((config) => Promise.resolve({ data: {}, status: 200, statusText: 'OK', headers: {}, config }))
    await iaApi.getOcrDocuments()
    expect(noterRequete).not.toHaveBeenCalled()
  })
})
