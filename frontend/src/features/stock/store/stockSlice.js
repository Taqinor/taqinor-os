import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import stockApi from '../../../api/stockApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'

// VX164 — garde anti-course PAR RESSOURCE sur les `update*.fulfilled` :
// deux PATCH rapides du MÊME enregistrement, résolus dans l'ordre INVERSE
// (le second dispatché répond avant le premier), ne doivent plus faire
// régresser l'écran vers le payload le plus ANCIEN. `seqMap[id]` retient le
// `requestId` (RTK) de la DERNIÈRE requête DISPATCHÉE pour cet id ; un
// `.fulfilled` dont le `requestId` ne correspond plus est un no-op silencieux
// — le payload le plus récemment DEMANDÉ gagne toujours, quel que soit
// l'ordre de résolution réseau.
function isStaleResourceUpdate(seqMap, id, requestId) {
  return seqMap[id] != null && seqMap[id] !== requestId
}

// ── Produits ───────────────────────────────────────────────────
// VX54 — la page 1 DRF (PAGE_SIZE=100) ne renvoyait que les 100 premiers
// produits : StockList et les KPI/graphiques du Dashboard étaient FAUX dès
// 101 produits, sans indicateur. On lit désormais TOUTES les pages, en
// parallèle borné (pas un escalier sériel).
export const fetchProduits = createAsyncThunk('stock/fetchProduits', async (_, { rejectWithValue }) => {
  try {
    const results = await fetchAllPages((page) => stockApi.getProduits({ page }).then((r) => r.data), { concurrency: 20 })
    return { results }
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const createProduit = createAsyncThunk('stock/createProduit', async (data, { rejectWithValue }) => {
  try {
    const res = await stockApi.createProduit(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateProduit = createAsyncThunk('stock/updateProduit', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await stockApi.updateProduit(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const deleteProduit = createAsyncThunk('stock/deleteProduit', async (id, { rejectWithValue }) => {
  try {
    const res = await stockApi.deleteProduit(id)
    // 200 = archived (has movements), 204 = deleted
    if (res.status === 200 && res.data?.archived) {
      return { id, archived: true, detail: res.data.detail }
    }
    return { id, archived: false }
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const unarchiveProduit = createAsyncThunk('stock/unarchiveProduit', async (id, { rejectWithValue }) => {
  try {
    const res = await stockApi.unarchiveProduit(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const forceDeleteArchivedProduit = createAsyncThunk('stock/forceDeleteArchivedProduit', async (id, { rejectWithValue }) => {
  try {
    const res = await stockApi.forceDeleteProduit(id)
    return { id, detail: res.data.detail }
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const fetchProduitsArchived = createAsyncThunk('stock/fetchProduitsArchived', async (_, { rejectWithValue }) => {
  try {
    const res = await stockApi.getProduitsArchived()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Catégories ─────────────────────────────────────────────────
export const fetchCategories = createAsyncThunk('stock/fetchCategories', async (_, { rejectWithValue }) => {
  try {
    const res = await stockApi.getCategories()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const createCategorie = createAsyncThunk('stock/createCategorie', async (data, { rejectWithValue }) => {
  try {
    const res = await stockApi.createCategorie(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Fournisseurs ───────────────────────────────────────────────
export const fetchFournisseurs = createAsyncThunk('stock/fetchFournisseurs', async (_, { rejectWithValue }) => {
  try {
    const res = await stockApi.getFournisseurs()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const createFournisseur = createAsyncThunk('stock/createFournisseur', async (data, { rejectWithValue }) => {
  try {
    const res = await stockApi.createFournisseur(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateFournisseur = createAsyncThunk('stock/updateFournisseur', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await stockApi.updateFournisseur(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const deleteFournisseur = createAsyncThunk('stock/deleteFournisseur', async (id, { rejectWithValue }) => {
  try {
    await stockApi.deleteFournisseur(id)
    return id
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateCategorie = createAsyncThunk('stock/updateCategorie', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await stockApi.updateCategorie(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const deleteCategorie = createAsyncThunk('stock/deleteCategorie', async (id, { rejectWithValue }) => {
  try {
    await stockApi.deleteCategorie(id)
    return id
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Mouvements ─────────────────────────────────────────────────
export const fetchMouvements = createAsyncThunk('stock/fetchMouvements', async (_, { rejectWithValue }) => {
  try {
    const res = await stockApi.getMouvements()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const createMouvement = createAsyncThunk('stock/createMouvement', async (data, { rejectWithValue }) => {
  try {
    const res = await stockApi.createMouvement(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

const stockSlice = createSlice({
  name: 'stock',
  initialState: {
    produits: [],
    produitsArchived: [],
    categories: [],
    fournisseurs: [],
    mouvements: [],
    loading: false,
    // VX165 — compteur de sondages EN VOL partagés par `fetchProduits`/
    // `fetchMouvements` (`loading` reste dérivé — rétrocompatible avec les
    // sélecteurs existants) : le premier résolu n'éteint plus le spinner
    // pendant qu'une requête sœur charge encore.
    pendingCount: 0,
    error: null,
    selectedProduit: null,
    // VX164 — requestId (RTK) de la DERNIÈRE update dispatchée, par id — une
    // map par ressource (produits/fournisseurs/catégories sont des tables
    // distinctes).
    produitUpdateSeq: {},
    fournisseurUpdateSeq: {},
    categorieUpdateSeq: {},
  },
  reducers: {
    setSelectedProduit(state, action) { state.selectedProduit = action.payload },
    clearError(state) { state.error = null },
  },
  extraReducers: (builder) => {
    // VX165 — voir `pendingCount` ci-dessus : `pending` incrémente,
    // `settleLoading` (fulfilled/rejected) décrémente et redérive `loading`.
    const pending = (state) => {
      state.pendingCount = (state.pendingCount || 0) + 1
      state.loading = true
      state.error = null
    }
    const settleLoading = (state) => {
      state.pendingCount = Math.max(0, (state.pendingCount || 0) - 1)
      state.loading = state.pendingCount > 0
    }
    const rejected = (state, action) => {
      settleLoading(state)
      state.error = action.payload
    }

    builder
      // Produits
      .addCase(fetchProduits.pending, pending)
      .addCase(fetchProduits.fulfilled, (state, action) => {
        settleLoading(state)
        state.produits = action.payload.results ?? action.payload
      })
      .addCase(fetchProduits.rejected, rejected)
      .addCase(createProduit.fulfilled, (state, action) => {
        state.produits.push(action.payload)
      })
      .addCase(updateProduit.pending, (state, action) => {
        state.produitUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(updateProduit.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.produitUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.produits.findIndex(p => p.id === action.payload.id)
        if (idx !== -1) state.produits[idx] = action.payload
      })
      .addCase(deleteProduit.fulfilled, (state, action) => {
        if (action.payload.archived) {
          const idx = state.produits.findIndex(p => p.id === action.payload.id)
          if (idx !== -1) state.produits[idx].is_archived = true
        } else {
          state.produits = state.produits.filter(p => p.id !== action.payload.id)
        }
      })
      .addCase(unarchiveProduit.fulfilled, (state, action) => {
        // Move from archived back to active
        state.produits = state.produits.filter(p => p.id !== action.payload.id)
        state.produitsArchived = state.produitsArchived.filter(p => p.id !== action.payload.id)
        if (!action.payload.is_archived) state.produits.push(action.payload)
      })
      .addCase(fetchProduitsArchived.fulfilled, (state, action) => {
        const list = action.payload.results ?? action.payload
        state.produitsArchived = list.filter(p => p.is_archived)
      })
      .addCase(forceDeleteArchivedProduit.fulfilled, (state, action) => {
        state.produitsArchived = state.produitsArchived.filter(p => p.id !== action.payload.id)
        state.produits = state.produits.filter(p => p.id !== action.payload.id)
      })

      // Catégories
      .addCase(fetchCategories.fulfilled, (state, action) => {
        state.categories = action.payload.results ?? action.payload
      })
      .addCase(createCategorie.fulfilled, (state, action) => {
        state.categories.push(action.payload)
      })

      // Fournisseurs
      .addCase(fetchFournisseurs.fulfilled, (state, action) => {
        state.fournisseurs = action.payload.results ?? action.payload
      })
      .addCase(createFournisseur.fulfilled, (state, action) => {
        state.fournisseurs.push(action.payload)
      })
      .addCase(updateFournisseur.pending, (state, action) => {
        state.fournisseurUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(updateFournisseur.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.fournisseurUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.fournisseurs.findIndex(f => f.id === action.payload.id)
        if (idx !== -1) state.fournisseurs[idx] = action.payload
      })
      .addCase(deleteFournisseur.fulfilled, (state, action) => {
        state.fournisseurs = state.fournisseurs.filter(f => f.id !== action.payload)
      })

      // Catégories (update/delete)
      .addCase(updateCategorie.pending, (state, action) => {
        state.categorieUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(updateCategorie.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.categorieUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.categories.findIndex(c => c.id === action.payload.id)
        if (idx !== -1) state.categories[idx] = action.payload
      })
      .addCase(deleteCategorie.fulfilled, (state, action) => {
        state.categories = state.categories.filter(c => c.id !== action.payload)
      })

      // Mouvements
      .addCase(fetchMouvements.pending, pending)
      .addCase(fetchMouvements.fulfilled, (state, action) => {
        settleLoading(state)
        state.mouvements = action.payload.results ?? action.payload
      })
      .addCase(fetchMouvements.rejected, rejected)
      .addCase(createMouvement.fulfilled, (state, action) => {
        state.mouvements.unshift(action.payload)
        // Met à jour la quantité du produit concerné
        const produit = state.produits.find(p => p.id === action.payload.produit)
        if (produit) produit.quantite_stock = action.payload.quantite_apres
      })
  },
})

export const { setSelectedProduit, clearError } = stockSlice.actions
export default stockSlice.reducer
