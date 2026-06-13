import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import savApi from '../../../api/savApi'

// On récupère TOUS les tickets (toutes pages, ?ouvert=tous) puis on filtre
// côté client — comme les slices CRM/chantiers.
export const fetchTickets = createAsyncThunk(
  'tickets/fetchAll',
  async (params, { rejectWithValue }) => {
    try {
      const q = { ouvert: 'tous', ...(params ?? {}) }
      const first = await savApi.getTickets(q)
      let data = first.data
      if (!data || !Array.isArray(data.results)) return data
      const all = [...data.results]
      let page = 2
      while (data.next && page <= 50) {
        const res = await savApi.getTickets({ ...q, page })
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

export const updateTicket = createAsyncThunk(
  'tickets/update',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const res = await savApi.updateTicket(id, data)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data ?? err.message)
    }
  },
)

const slice = createSlice({
  name: 'tickets',
  initialState: { items: [], loading: false, error: null },
  reducers: {
    upsertTicket(state, action) {
      const i = state.items.findIndex((x) => x.id === action.payload.id)
      if (i === -1) state.items.unshift(action.payload)
      else state.items[i] = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchTickets.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchTickets.fulfilled, (state, action) => {
        state.loading = false
        state.items = action.payload?.results ?? action.payload ?? []
      })
      .addCase(fetchTickets.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })
      .addCase(updateTicket.fulfilled, (state, action) => {
        const i = state.items.findIndex((x) => x.id === action.payload.id)
        if (i !== -1) state.items[i] = action.payload
      })
  },
})

export const { upsertTicket } = slice.actions
export default slice.reducer
