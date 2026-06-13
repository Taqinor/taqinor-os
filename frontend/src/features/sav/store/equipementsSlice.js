import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import savApi from '../../../api/savApi'

// Récupère TOUTES les pages (DRF pagine à 100), comme les slices CRM/chantiers.
export const fetchEquipements = createAsyncThunk(
  'equipements/fetchAll',
  async (params, { rejectWithValue }) => {
    try {
      const first = await savApi.getEquipements(params)
      let data = first.data
      if (!data || !Array.isArray(data.results)) return data
      const all = [...data.results]
      let page = 2
      while (data.next && page <= 50) {
        const res = await savApi.getEquipements({ ...(params ?? {}), page })
        data = res.data
        all.push(...(data.results ?? []))
        page += 1
      }
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
