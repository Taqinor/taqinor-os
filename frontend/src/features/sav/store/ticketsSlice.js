import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import savApi from '../../../api/savApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'

// On récupère TOUS les tickets (toutes pages, ?ouvert=tous) puis on filtre
// côté client — comme les slices CRM/chantiers.
// VX54 — était un `while` SÉRIEL (un aller-retour réseau par page ; gèle les
// écrans TERRAIN plusieurs secondes à 250-500 ms de RTT) ; désormais
// parallèle borné.
export const fetchTickets = createAsyncThunk(
  'tickets/fetchAll',
  async (params, { rejectWithValue }) => {
    try {
      const q = { ouvert: 'tous', ...(params ?? {}) }
      const all = await fetchAllPages(
        (page) => savApi.getTickets({ ...q, page }).then((r) => r.data),
        { concurrency: 20 },
      )
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
