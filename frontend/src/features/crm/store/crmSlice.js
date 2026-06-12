import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import crmApi from '../../../api/crmApi'

export const fetchClients = createAsyncThunk('crm/fetchClients', async (_, { rejectWithValue }) => {
  try {
    const res = await crmApi.getClients()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const createClient = createAsyncThunk('crm/createClient', async (data, { rejectWithValue }) => {
  try {
    const res = await crmApi.createClient(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateClient = createAsyncThunk('crm/updateClient', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await crmApi.updateClient(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const deleteClient = createAsyncThunk('crm/deleteClient', async (id, { rejectWithValue }) => {
  try {
    await crmApi.deleteClient(id)
    return id
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const fetchLeads = createAsyncThunk('crm/fetchLeads', async (params, { rejectWithValue }) => {
  try {
    const res = await crmApi.getLeads(params)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const createLead = createAsyncThunk('crm/createLead', async (data, { rejectWithValue }) => {
  try {
    const res = await crmApi.createLead(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const updateLead = createAsyncThunk('crm/updateLead', async ({ id, data }, { rejectWithValue }) => {
  try {
    const res = await crmApi.updateLead(id, data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

const crmSlice = createSlice({
  name: 'crm',
  initialState: {
    clients: [],
    leads: [],
    leadsLoading: false,
    loading: false,
    error: null,
    selectedClient: null,
  },
  reducers: {
    setSelectedClient(state, action) { state.selectedClient = action.payload },
    clearError(state) { state.error = null },
  },
  extraReducers: (builder) => {
    const pending = (state) => { state.loading = true; state.error = null }
    const rejected = (state, action) => { state.loading = false; state.error = action.payload }

    builder
      .addCase(fetchClients.pending, pending)
      .addCase(fetchClients.fulfilled, (state, action) => {
        state.loading = false
        state.clients = action.payload.results ?? action.payload
      })
      .addCase(fetchClients.rejected, rejected)
      .addCase(createClient.fulfilled, (state, action) => { state.clients.push(action.payload) })
      .addCase(updateClient.fulfilled, (state, action) => {
        const idx = state.clients.findIndex(c => c.id === action.payload.id)
        if (idx !== -1) state.clients[idx] = action.payload
      })
      .addCase(deleteClient.fulfilled, (state, action) => {
        state.clients = state.clients.filter(c => c.id !== action.payload)
      })
      .addCase(fetchLeads.pending, (state) => { state.leadsLoading = true; state.error = null })
      .addCase(fetchLeads.fulfilled, (state, action) => {
        state.leadsLoading = false
        state.leads = action.payload.results ?? action.payload
      })
      .addCase(fetchLeads.rejected, (state, action) => {
        state.leadsLoading = false
        state.error = action.payload
      })
      .addCase(createLead.fulfilled, (state, action) => {
        state.leads.unshift(action.payload)
      })
      .addCase(updateLead.fulfilled, (state, action) => {
        const idx = state.leads.findIndex(l => l.id === action.payload.id)
        if (idx !== -1) state.leads[idx] = action.payload
      })
  },
})

export const { setSelectedClient, clearError } = crmSlice.actions
export default crmSlice.reducer
