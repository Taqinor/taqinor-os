import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import crmApi from '../../../api/crmApi'
import { fetchAllPages } from '../../../utils/fetchAllPages'

// VX54 — la page 1 DRF (PAGE_SIZE=100) ne renvoyait que les 100 premiers
// clients : FAUX dès 101 clients. Toutes les pages sont désormais lues, en
// parallèle borné.
export const fetchClients = createAsyncThunk('crm/fetchClients', async (_, { rejectWithValue }) => {
  try {
    const results = await fetchAllPages((page) => crmApi.getClients({ page }).then((r) => r.data), { concurrency: 20 })
    return { results }
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
    // Le kanban doit voir TOUS les leads : on suit la pagination DRF
    // (PAGE_SIZE 100) jusqu'au bout au lieu de s'arrêter à la première page.
    // VX54 — était un `while` SÉRIEL (un aller-retour réseau par page, gel de
    // plusieurs secondes à 250-500 ms de RTT) ; désormais parallèle borné.
    const all = await fetchAllPages(
      (page) => crmApi.getLeads({ ...(params ?? {}), page }).then((r) => r.data),
      { concurrency: 20 },
    )
    return all
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

export const archiveLead = createAsyncThunk('crm/archiveLead', async (id, { rejectWithValue }) => {
  try {
    const res = await crmApi.archiverLead(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const restoreLead = createAsyncThunk('crm/restoreLead', async (id, { rejectWithValue }) => {
  try {
    const res = await crmApi.restaurerLead(id)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const deleteLead = createAsyncThunk('crm/deleteLead', async (id, { rejectWithValue }) => {
  try {
    // VX96 — la suppression est désormais un SOFT-DELETE réversible : la
    // réponse porte `corbeille_id`, l'entrée de corbeille à restaurer si
    // l'utilisateur clique « Annuler » (fenêtre 30 min, TrashViewSet).
    const res = await crmApi.deleteLead(id)
    return { id, corbeille_id: res?.data?.corbeille_id ?? null }
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
    // Changement d'étape optimiste (drag-and-drop kanban) : l'UI bouge tout de
    // suite, le conteneur redéclenche cette action avec l'ancienne étape si le
    // PATCH échoue (retour-arrière).
    leadStagePatched(state, action) {
      const { id, stage } = action.payload
      const lead = state.leads.find(l => l.id === id)
      if (lead) lead.stage = stage
    },
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
      .addCase(archiveLead.fulfilled, (state, action) => {
        const idx = state.leads.findIndex(l => l.id === action.payload.id)
        if (idx !== -1) state.leads[idx] = action.payload
      })
      .addCase(restoreLead.fulfilled, (state, action) => {
        const idx = state.leads.findIndex(l => l.id === action.payload.id)
        if (idx !== -1) state.leads[idx] = action.payload
      })
      .addCase(deleteLead.fulfilled, (state, action) => {
        // VX96 — payload = { id, corbeille_id } (soft-delete réversible).
        const deletedId = action.payload?.id ?? action.payload
        state.leads = state.leads.filter(l => l.id !== deletedId)
      })
  },
})

export const { setSelectedClient, clearError, leadStagePatched } = crmSlice.actions
export default crmSlice.reducer
