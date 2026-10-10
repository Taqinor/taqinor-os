import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import React from 'react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { renderHook, act, waitFor } from '@testing-library/react'

/* APRF8 — comportemental : un faux serveur HTTP (adaptateur axios de
   l'instance partagée) applique la pagination DRF réelle (50/page) et COMPTE
   les requêtes de lecture reçues. Envoyer UN devis d'un store de 2 000 :
   au plus 1 lecture (GET devis/<id>/), la ligne a le nouveau statut, les
   1 999 autres sont inchangées et dans le même ordre. Jamais un espion sur
   `dispatch`. */
import api from '../../../api/axios'
import ventesReducer, { fetchDevis } from '../../../features/ventes/store/ventesSlice'
import { useDevisEnvoi } from './useDevisEnvoi'

const N = 2000
const PAGE = 50
let serveur
let lectures
const adapterInitial = api.defaults.adapter

function fauxServeur() {
  serveur = Array.from({ length: N }, (_, i) => ({
    id: i + 1, reference: `DEV-${i + 1}`, statut: 'brouillon', is_active: true,
  }))
  lectures = []
  api.defaults.adapter = async (config) => {
    const url = config.url
    const reponse = (data, status = 200) => ({ data, status, statusText: 'OK', headers: {}, config })
    if (config.method === 'get') lectures.push(url)
    let m
    if (config.method === 'get' && /\/ventes\/devis\/$/.test(url)) {
      const page = Number(config.params?.page ?? 1)
      const debut = (page - 1) * PAGE
      return reponse({
        count: N,
        next: debut + PAGE < N ? `?page=${page + 1}` : null,
        results: serveur.slice(debut, debut + PAGE).map((d) => ({ ...d })),
      })
    }
    if (config.method === 'get' && (m = url.match(/\/ventes\/devis\/(\d+)\/$/))) {
      return reponse({ ...serveur.find((d) => d.id === Number(m[1])) })
    }
    if (config.method === 'post' && (m = url.match(/\/ventes\/devis\/(\d+)\/share-link\/$/))) {
      serveur.find((d) => d.id === Number(m[1])).statut = 'envoye'
      return reponse({ token: 'tok', path: '/proposition/tok' })
    }
    throw Object.assign(new Error(`non géré ${config.method} ${url}`), { config })
  }
}

const monter = () => {
  const store = configureStore({ reducer: { ventes: ventesReducer } })
  const wrapper = ({ children }) => <Provider store={store}>{children}</Provider>
  const hook = renderHook(() => useDevisEnvoi({
    dispatch: store.dispatch, setPreviewDevis: () => {}, setStatutActionId: () => {},
    highlightId: null, highlightedDevis: null, loading: false,
    searchParams: new URLSearchParams(), setSearchParams: () => {},
  }), { wrapper })
  return { store, hook }
}

describe('APRF8 — action unitaire = au plus 1 lecture', () => {
  beforeEach(fauxServeur)
  afterEach(() => { api.defaults.adapter = adapterInitial })

  it('envoyer 1 devis sur 2 000 : <= 1 lecture, ligne patchée, autres intactes', async () => {
    const { store, hook } = monter()
    await store.dispatch(fetchDevis())
    expect(lectures.length).toBe(N / PAGE) // 40 pages : la relecture complète
    const avant = store.getState().ventes.devis
    expect(avant).toHaveLength(N)
    lectures.length = 0

    await act(async () => { await hook.result.current.handleCopierLienProposition(avant[41]) })
    await waitFor(() => expect(store.getState().ventes.devis[41].statut).toBe('envoye'))

    expect(lectures.length).toBeLessThanOrEqual(1)
    const apres = store.getState().ventes.devis
    expect(apres.map((d) => d.id)).toEqual(avant.map((d) => d.id))
    apres.forEach((d, i) => { if (i !== 41) expect(d).toBe(avant[i]) })

    // CLAUSE PERSISTANCE : une relecture complète montre le même statut.
    await store.dispatch(fetchDevis())
    expect(store.getState().ventes.devis[41].statut).toBe('envoye')
    expect(store.getState().ventes.devis.filter((d) => d.statut === 'envoye')).toHaveLength(1)
  })
})
