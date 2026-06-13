import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import installationsApi from '../../../api/installationsApi'

// Récupère TOUTES les pages (DRF pagine à 100), comme le slice CRM.
export const fetchInstallations = createAsyncThunk(
  'installations/fetchAll',
  async (params, { rejectWithValue }) => {
    try {
      const first = await installationsApi.getInstallations(params)
      let data = first.data
      if (!data || !Array.isArray(data.results)) return data
      const all = [...data.results]
      let page = 2
      while (data.next && page <= 50) {
        const res = await installationsApi.getInstallations({ ...(params ?? {}), page })
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
