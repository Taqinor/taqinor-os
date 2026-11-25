import { describe, it, expect, vi } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'

// ADEV35 — le store des bons de commande lit TOUTES les pages DRF
// `{count,next,results}` (sonde : count 57, 50 reçus sur la page 1) ; une
// liste de 10 éléments ne fait qu'une requête. Le vrai thunk + le vrai réducteur
// tournent ; seul le réseau (ventesApi) est simulé, avec la forme paginée réelle.
vi.mock('../../../api/ventesApi', () => ({
  default: { getBonsCommande: vi.fn(), getDevis: vi.fn(), getDevisSynthese: vi.fn() },
}))

import ventesApi from '../../../api/ventesApi'
import ventesReducer, { fetchBonsCommande, fetchDevis } from './ventesSlice'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const bc = (i) => ({ id: i, reference: `BC-${i}` })
const store = () => configureStore({ reducer: { ventes: ventesReducer } })

describe('ADEV35 — fetchBonsCommande lit toutes les pages', () => {
  it('57 BC sur deux pages → 57 dans le store', async () => {
    ventesApi.getBonsCommande.mockImplementation(({ page } = {}) => Promise.resolve({
      data: page === 2
        ? { count: 57, next: null, results: Array.from({ length: 7 }, (_, i) => bc(51 + i)) }
        : { count: 57, next: '?page=2', results: Array.from({ length: 50 }, (_, i) => bc(i + 1)) },
    }))
    const s = store()
    await s.dispatch(fetchBonsCommande())
    expect(s.getState().ventes.bonsCommande).toHaveLength(57)
  })

  it('une liste de 10 éléments fait une seule requête', async () => {
    ventesApi.getBonsCommande.mockReset()
    ventesApi.getBonsCommande.mockResolvedValue({
      data: { count: 10, next: null, results: Array.from({ length: 10 }, (_, i) => bc(i + 1)) },
    })
    const s = store()
    await s.dispatch(fetchBonsCommande())
    expect(ventesApi.getBonsCommande).toHaveBeenCalledTimes(1)
    expect(s.getState().ventes.bonsCommande).toHaveLength(10)
  })
})

// T4-X4-005 — l'écran Devis demande UNE page (jamais toutes) et la synthèse
// servie de son en-tête ; une synthèse en échec ne vide pas la page, une page
// en échec ne vide pas les lignes déjà affichées.
describe('T4-X4-005 — fetchDevis(requete) : une page et sa synthèse', () => {
  const requete = { page: 2, page_size: 25, actifs: 1 }
  const page = (n) => ({ data: { count: 60, next: null, results: Array.from({ length: n }, (_, i) => ({ id: i + 1 })) } })

  it('une seule requête de page, compte et synthèse rangés', async () => {
    ventesApi.getDevis.mockReset().mockResolvedValue(page(25))
    ventesApi.getDevisSynthese.mockReset().mockResolvedValue({ data: exempleContrat('ventes', 'devis_synthese') })
    const s = store()
    await s.dispatch(fetchDevis(requete))
    expect(ventesApi.getDevis).toHaveBeenCalledTimes(1)
    expect(ventesApi.getDevis.mock.calls[0][0]).toEqual(requete)
    const v = s.getState().ventes
    expect(v.devis).toHaveLength(25)
    expect(v.devisCount).toBe(60)
    expect(v.devisRequete).toEqual(requete)
    expect(v.devisSynthese.total).toBe(exempleContrat('ventes', 'devis_synthese').total)
    expect(v.devisSyntheseEchec).toBe(false)
  })

  it('synthèse en échec : la page arrive quand même, échec signalé', async () => {
    ventesApi.getDevis.mockReset().mockResolvedValue(page(3))
    ventesApi.getDevisSynthese.mockReset().mockRejectedValue(new Error('500'))
    const s = store()
    await s.dispatch(fetchDevis(requete))
    expect(s.getState().ventes.devis).toHaveLength(3)
    expect(s.getState().ventes.devisSyntheseEchec).toBe(true)
  })

  it('page en échec : les lignes déjà affichées restent, l’erreur est posée', async () => {
    ventesApi.getDevis.mockReset().mockResolvedValueOnce(page(4)).mockRejectedValueOnce({ message: 'timeout' })
    ventesApi.getDevisSynthese.mockReset().mockResolvedValue({ data: exempleContrat('ventes', 'devis_synthese') })
    const s = store()
    await s.dispatch(fetchDevis(requete))
    await s.dispatch(fetchDevis({ ...requete, page: 3 }))
    expect(s.getState().ventes.devis).toHaveLength(4)
    expect(s.getState().ventes.error).toBe('timeout')
  })
})
