import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import installationsApi from '../../../api/installationsApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'

// Récupère TOUTES les pages (DRF pagine à 100), comme le slice CRM.
// VX54 — était un `while` SÉRIEL (un aller-retour réseau par page ; gèle les
// écrans TERRAIN plusieurs secondes à 250-500 ms de RTT) ; désormais
// parallèle borné.
export const fetchInstallations = createAsyncThunk(
  'installations/fetchAll',
  async (params, { rejectWithValue }) => {
    try {
      const all = await fetchAllPages(
        (page) => installationsApi.getInstallations({ ...(params ?? {}), page }).then((r) => r.data),
        { concurrency: 20 },
      )
      return all
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

export const updateInstallation = createAsyncThunk(
  'installations/update',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const res = await installationsApi.updateInstallation(id, data)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

const slice = createSlice({
  name: 'installations',
  initialState: { items: [], loading: false, error: null },
  reducers: {
    upsertInstallation(state, action) {
      const i = state.items.findIndex((x) => x.id === action.payload.id)
      if (i === -1) state.items.unshift(action.payload)
      else state.items[i] = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchInstallations.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchInstallations.fulfilled, (state, action) => {
        state.loading = false
        state.items = action.payload?.results ?? action.payload ?? []
      })
      .addCase(fetchInstallations.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })
      .addCase(updateInstallation.fulfilled, (state, action) => {
        const i = state.items.findIndex((x) => x.id === action.payload.id)
        if (i !== -1) state.items[i] = action.payload
      })
  },
})

export const { upsertInstallation } = slice.actions
export default slice.reducer
