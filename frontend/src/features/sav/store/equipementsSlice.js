import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import savApi from '../../../api/savApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'

// Récupère TOUTES les pages (DRF pagine à 100), comme les slices CRM/chantiers.
// VX54 — était un `while` SÉRIEL (un aller-retour réseau par page ; gèle les
// écrans TERRAIN plusieurs secondes à 250-500 ms de RTT) ; désormais
// parallèle borné.
export const fetchEquipements = createAsyncThunk(
  'equipements/fetchAll',
  async (params, { rejectWithValue }) => {
    try {
      const all = await fetchAllPages(
        (page) => savApi.getEquipements({ ...(params ?? {}), page }).then((r) => r.data),
        { concurrency: 20 },
      )
      return all
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

const slice = createSlice({
  name: 'equipements',
  initialState: { items: [], loading: false, error: null },
  reducers: {
    upsertEquipement(state, action) {
      const i = state.items.findIndex((x) => x.id === action.payload.id)
      if (i === -1) state.items.unshift(action.payload)
      else state.items[i] = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchEquipements.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchEquipements.fulfilled, (state, action) => {
        state.loading = false
        state.items = action.payload?.results ?? action.payload ?? []
      })
      .addCase(fetchEquipements.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })
  },
})

export const { upsertEquipement } = slice.actions
export default slice.reducer
