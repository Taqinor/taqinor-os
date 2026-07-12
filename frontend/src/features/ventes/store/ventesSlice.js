import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import ventesApi from '../../../api/ventesApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'
import { createCancellableThunk, dedupeInFlight } from '../../../lib/thunkHelpers'

// VX164 — garde anti-course PAR RESSOURCE sur les `update*/patch*.fulfilled` :
// deux PATCH rapides du MÊME devis/BC/facture, résolus dans l'ordre INVERSE
// (le second dispatché répond avant le premier), ne doivent plus faire
// régresser l'écran vers le payload le plus ANCIEN. `seqMap[id]` retient le
// `requestId` (RTK) de la DERNIÈRE requête DISPATCHÉE pour cet id ; un
// `.fulfilled` dont le `requestId` ne correspond plus est un no-op silencieux
// — le payload le plus récemment DEMANDÉ gagne toujours, quel que soit
// l'ordre de résolution réseau.
function isStaleResourceUpdate(seqMap, id, requestId) {
  return seqMap[id] != null && seqMap[id] !== requestId
}

// ── Devis ──────────────────────────────────────────────
// VX54 — la page 1 DRF (PAGE_SIZE=100) ne renvoyait que les 100 premiers
// devis : DevisList et les KPI du Dashboard étaient FAUX dès 101 devis. On lit
// désormais TOUTES les pages, en parallèle mais borné à ~3-5 MAX (au lieu du
// ~20 par défaut) tant que QPERF1 (N+1 backend : ~38-109 requêtes SQL PAR
// page de devis) n'est pas corrigé — sinon ~20 pages parallèles = ~2 000
// requêtes SQL quasi simultanées auto-infligées au Postgres à chaque montage
// de DevisList. Relever cette borne quand QPERF1 atterrit (@coord QPERF1).
const DEVIS_PAGE_CONCURRENCY = 5

// VX55 — `signal` natif de createAsyncThunk câblé jusqu'à l'appel axios :
// `thunk.abort()` (cleanup d'effet au démontage de DevisList) annule les pages
// en vol au lieu de laisser une réponse tardive écraser l'état après navigation.
// VX163 — enrobé par `createCancellableThunk` (annulation → `meta.aborted ===
// true`, propre plutôt qu'un `rejectWithValue`) + dé-duplication en vol (deux
// montages simultanés de DevisList ne déclenchent qu'UNE seule pagination).
export const fetchDevis = createCancellableThunk('ventes/fetchDevis', (_, { signal }) =>
  dedupeInFlight('ventes/fetchDevis', () =>
    fetchAllPages((page) => ventesApi.getDevis({ page }, { signal }).then((r) => r.data), { concurrency: DEVIS_PAGE_CONCURRENCY })
      .then((results) => ({ results })),
  ),
)

export const createDevis = createAsyncThunk('ventes/createDevis', async (data, { rejectWithValue }) => {
  try {
    const res = await ventesApi.createDevis(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateDevis = createAsyncThunk('ventes/updateDevis', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.updateDevis(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const genererPdfDevis = createAsyncThunk('ventes/genererPdfDevis', async (arg, { rejectWithValue }) => {
  // arg : id seul, ou { id, options } avec les options de format PDF
  const { id, options } = (arg && typeof arg === 'object') ? arg : { id: arg, options: {} }
  try {
    const res = await ventesApi.genererPdfDevis(id, options)
    return { id, ...res.data }
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const convertirDevisEnBC = createAsyncThunk('ventes/convertirDevisEnBC', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.convertirDevisEnBC(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const patchDevis = createAsyncThunk('ventes/patchDevis', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.patchDevis(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Lignes de devis ────────────────────────────────────
export const addLigneDevis = createAsyncThunk('ventes/addLigneDevis', async (data, { rejectWithValue }) => {
  try {
    const res = await ventesApi.createLigneDevis(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateLigneDevis = createAsyncThunk('ventes/updateLigneDevis', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.updateLigneDevis(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const removeLigneDevis = createAsyncThunk('ventes/removeLigneDevis', async (id, { rejectWithValue }) => {
  try {
    await ventesApi.deleteLigneDevis(id)
    return id
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Bons de commande ───────────────────────────────────
export const fetchBonsCommande = createAsyncThunk('ventes/fetchBonsCommande', async (_, { rejectWithValue }) => {
  try {
    const res = await ventesApi.getBonsCommande()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const createBonCommande = createAsyncThunk('ventes/createBonCommande', async (data, { rejectWithValue }) => {
  try {
    const res = await ventesApi.createBonCommande(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateBonCommande = createAsyncThunk('ventes/updateBonCommande', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.patchBonCommande(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const confirmerBC = createAsyncThunk('ventes/confirmerBC', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.confirmerBC(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const marquerLivreBC = createAsyncThunk('ventes/marquerLivreBC', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.marquerLivreBC(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const annulerBC = createAsyncThunk('ventes/annulerBC', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.annulerBC(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// XSAL12 — livraison partielle : { lignes: [{ligne_devis, quantite}], ... }.
export const livrerPartielBC = createAsyncThunk(
  'ventes/livrerPartielBC', async ({ id, data }, { rejectWithValue }) => {
    try {
      const res = await ventesApi.livrerPartielBC(id, data)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  })

export const creerFactureFromBC = createAsyncThunk('ventes/creerFactureFromBC', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.creerFactureBC(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Factures ───────────────────────────────────────────
// VX54 — même bug de troncature silencieuse que fetchDevis : toutes les
// pages désormais lues, en parallèle borné (les factures n'ont pas le N+1
// QPERF1 des devis, donc la borne par défaut ~20 s'applique).
// VX163 — `{signal}` câblé + dé-duplication en vol (même patron que fetchDevis).
export const fetchFactures = createCancellableThunk('ventes/fetchFactures', (_, { signal }) =>
  dedupeInFlight('ventes/fetchFactures', () =>
    fetchAllPages((page) => ventesApi.getFactures({ page }, { signal }).then((r) => r.data), { concurrency: 20 })
      .then((results) => ({ results })),
  ),
)

export const createFacture = createAsyncThunk('ventes/createFacture', async (data, { rejectWithValue }) => {
  try {
    const res = await ventesApi.createFacture(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateFacture = createAsyncThunk('ventes/updateFacture', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.updateFacture(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const patchFacture = createAsyncThunk('ventes/patchFacture', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.patchFacture(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const genererPdfFacture = createAsyncThunk('ventes/genererPdfFacture', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.genererPdfFacture(id)
    return { id, ...res.data }
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const envoyerEmailFacture = createAsyncThunk('ventes/envoyerEmailFacture', async ({ id, email }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.envoyerEmailFacture(id, email)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const emettreFacture = createAsyncThunk('ventes/emettreFacture', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.emettreFacture(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const marquerPayeeFacture = createAsyncThunk('ventes/marquerPayeeFacture', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.marquerPayeeFacture(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const annulerFacture = createAsyncThunk('ventes/annulerFacture', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.annulerFacture(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Lignes de facture ──────────────────────────────────
export const addLigneFacture = createAsyncThunk('ventes/addLigneFacture', async (data, { rejectWithValue }) => {
  try {
    const res = await ventesApi.createLigneFacture(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateLigneFacture = createAsyncThunk('ventes/updateLigneFacture', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await ventesApi.updateLigneFacture(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const removeLigneFacture = createAsyncThunk('ventes/removeLigneFacture', async (id, { rejectWithValue }) => {
  try {
    await ventesApi.deleteLigneFacture(id)
    return id
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

const ventesSlice = createSlice({
  name: 'ventes',
  initialState: {
    devis: [],
    bonsCommande: [],
    factures: [],
    loading: false,
    // VX165 — compteur de sondages EN VOL partagés par `fetchDevis`/
    // `fetchBonsCommande`/`fetchFactures` : `loading` reste dérivé de ce
    // compteur (rétrocompatible avec les sélecteurs existants), mais
    // n'éteint plus tant qu'une requête sœur charge encore.
    pendingCount: 0,
    error: null,
    pdfLoading: false,
    // VX164 — requestId (RTK) de la DERNIÈRE update/patch dispatchée, par id
    // — une map par ressource (devis/BC/factures sont des tables distinctes).
    devisUpdateSeq: {},
    bonCommandeUpdateSeq: {},
    factureUpdateSeq: {},
  },
  reducers: {
    clearError(state) { state.error = null },
  },
  extraReducers: (builder) => {
    // VX165 — `pending` incrémente le compteur PARTAGÉ ; `settleLoading`
    // (appelé par CHAQUE fulfilled/rejected sœur) le décrémente et redérive
    // `loading` — le premier résolu n'éteint plus le spinner pendant que
    // `fetchDevis`/`fetchBonsCommande`/`fetchFactures` sœurs chargent encore.
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
      // Devis
      .addCase(fetchDevis.pending, pending)
      .addCase(fetchDevis.fulfilled, (state, action) => {
        settleLoading(state)
        state.devis = action.payload.results ?? action.payload
      })
      .addCase(fetchDevis.rejected, rejected)
      .addCase(createDevis.fulfilled, (state, action) => { state.devis.push(action.payload) })
      .addCase(updateDevis.pending, (state, action) => {
        state.devisUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(updateDevis.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.devisUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.devis.findIndex(d => d.id === action.payload.id)
        if (idx !== -1) state.devis[idx] = action.payload
      })
      .addCase(patchDevis.pending, (state, action) => {
        state.devisUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(patchDevis.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.devisUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.devis.findIndex(d => d.id === action.payload.id)
        if (idx !== -1) state.devis[idx] = action.payload
      })
      .addCase(convertirDevisEnBC.fulfilled, (state, action) => {
        state.bonsCommande.push(action.payload)
      })
      .addCase(genererPdfDevis.pending, (state) => { state.pdfLoading = true })
      .addCase(genererPdfDevis.fulfilled, (state) => { state.pdfLoading = false })
      .addCase(genererPdfDevis.rejected, (state) => { state.pdfLoading = false })

      // Bons de commande
      .addCase(fetchBonsCommande.pending, pending)
      .addCase(fetchBonsCommande.fulfilled, (state, action) => {
        settleLoading(state)
        state.bonsCommande = action.payload.results ?? action.payload
      })
      .addCase(fetchBonsCommande.rejected, rejected)
      .addCase(createBonCommande.fulfilled, (state, action) => {
        state.bonsCommande.push(action.payload)
      })
      .addCase(updateBonCommande.pending, (state, action) => {
        state.bonCommandeUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(updateBonCommande.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.bonCommandeUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.bonsCommande.findIndex(b => b.id === action.payload.id)
        if (idx !== -1) state.bonsCommande[idx] = action.payload
      })
      .addCase(confirmerBC.fulfilled, (state, action) => {
        const idx = state.bonsCommande.findIndex(b => b.id === action.payload.id)
        if (idx !== -1) state.bonsCommande[idx] = action.payload
      })
      .addCase(marquerLivreBC.fulfilled, (state, action) => {
        const idx = state.bonsCommande.findIndex(b => b.id === action.payload.id)
        if (idx !== -1) state.bonsCommande[idx] = action.payload
      })
      .addCase(annulerBC.fulfilled, (state, action) => {
        const idx = state.bonsCommande.findIndex(b => b.id === action.payload.id)
        if (idx !== -1) state.bonsCommande[idx] = action.payload
      })
      .addCase(livrerPartielBC.fulfilled, (state, action) => {
        const idx = state.bonsCommande.findIndex(b => b.id === action.payload.id)
        if (idx !== -1) state.bonsCommande[idx] = action.payload
      })
      .addCase(creerFactureFromBC.fulfilled, (state, action) => {
        state.factures.push(action.payload)
        // mark has_facture on the related BC
        const bc = state.bonsCommande.find(b => b.id === action.payload.bon_commande)
        if (bc) bc.has_facture = true
      })

      // Factures
      .addCase(fetchFactures.pending, pending)
      .addCase(fetchFactures.fulfilled, (state, action) => {
        settleLoading(state)
        state.factures = action.payload.results ?? action.payload
      })
      .addCase(fetchFactures.rejected, rejected)
      .addCase(createFacture.fulfilled, (state, action) => { state.factures.push(action.payload) })
      .addCase(updateFacture.pending, (state, action) => {
        state.factureUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(updateFacture.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.factureUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.factures.findIndex(f => f.id === action.payload.id)
        if (idx !== -1) state.factures[idx] = action.payload
      })
      .addCase(patchFacture.pending, (state, action) => {
        state.factureUpdateSeq[action.meta.arg.id] = action.meta.requestId
      })
      .addCase(patchFacture.fulfilled, (state, action) => {
        if (isStaleResourceUpdate(state.factureUpdateSeq, action.payload.id, action.meta.requestId)) return
        const idx = state.factures.findIndex(f => f.id === action.payload.id)
        if (idx !== -1) state.factures[idx] = action.payload
      })
      .addCase(emettreFacture.fulfilled, (state, action) => {
        const idx = state.factures.findIndex(f => f.id === action.payload.id)
        if (idx !== -1) state.factures[idx] = action.payload
      })
      .addCase(marquerPayeeFacture.fulfilled, (state, action) => {
        const idx = state.factures.findIndex(f => f.id === action.payload.id)
        if (idx !== -1) state.factures[idx] = action.payload
      })
      .addCase(annulerFacture.fulfilled, (state, action) => {
        const idx = state.factures.findIndex(f => f.id === action.payload.id)
        if (idx !== -1) state.factures[idx] = action.payload
      })
      .addCase(genererPdfFacture.pending, (state) => { state.pdfLoading = true })
      .addCase(genererPdfFacture.fulfilled, (state) => { state.pdfLoading = false })
      .addCase(genererPdfFacture.rejected, (state) => { state.pdfLoading = false })
  },
})

export const { clearError } = ventesSlice.actions
export default ventesSlice.reducer
