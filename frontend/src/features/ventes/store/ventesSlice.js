import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import ventesApi from '../../../api/ventesApi'

// ── Devis ──────────────────────────────────────────────
export const fetchDevis = createAsyncThunk('ventes/fetchDevis', async (_, { rejectWithValue }) => {
  try {
    const res = await ventesApi.getDevis()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

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

export const creerFactureFromBC = createAsyncThunk('ventes/creerFactureFromBC', async (id, { rejectWithValue }) => {
  try {
    const res = await ventesApi.creerFactureBC(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

// ── Factures ───────────────────────────────────────────
export const fetchFactures = createAsyncThunk('ventes/fetchFactures', async (_, { rejectWithValue }) => {
  try {
    const res = await ventesApi.getFactures()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

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
    error: null,
    pdfLoading: false,
  },
  reducers: {
    clearError(state) { state.error = null },
  },
  extraReducers: (builder) => {
    const pending = (state) => { state.loading = true; state.error = null }
    const rejected = (state, action) => { state.loading = false; state.error = action.payload }

    builder
      // Devis
      .addCase(fetchDevis.pending, pending)
      .addCase(fetchDevis.fulfilled, (state, action) => {
        state.loading = false
        state.devis = action.payload.results ?? action.payload
      })
      .addCase(fetchDevis.rejected, rejected)
      .addCase(createDevis.fulfilled, (state, action) => { state.devis.push(action.payload) })
      .addCase(updateDevis.fulfilled, (state, action) => {
        const idx = state.devis.findIndex(d => d.id === action.payload.id)
        if (idx !== -1) state.devis[idx] = action.payload
      })
      .addCase(patchDevis.fulfilled, (state, action) => {
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
        state.loading = false
        state.bonsCommande = action.payload.results ?? action.payload
      })
      .addCase(fetchBonsCommande.rejected, rejected)
      .addCase(createBonCommande.fulfilled, (state, action) => {
        state.bonsCommande.push(action.payload)
      })
      .addCase(updateBonCommande.fulfilled, (state, action) => {
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
      .addCase(creerFactureFromBC.fulfilled, (state, action) => {
        state.factures.push(action.payload)
        // mark has_facture on the related BC
        const bc = state.bonsCommande.find(b => b.id === action.payload.bon_commande)
        if (bc) bc.has_facture = true
      })

      // Factures
      .addCase(fetchFactures.pending, pending)
      .addCase(fetchFactures.fulfilled, (state, action) => {
        state.loading = false
        state.factures = action.payload.results ?? action.payload
      })
      .addCase(fetchFactures.rejected, rejected)
      .addCase(createFacture.fulfilled, (state, action) => { state.factures.push(action.payload) })
      .addCase(updateFacture.fulfilled, (state, action) => {
        const idx = state.factures.findIndex(f => f.id === action.payload.id)
        if (idx !== -1) state.factures[idx] = action.payload
      })
      .addCase(patchFacture.fulfilled, (state, action) => {
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
