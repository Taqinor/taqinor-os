import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../../../api/axios'

export const fetchDashboard = createAsyncThunk(
  'reporting/fetchDashboard',
  async (_, { rejectWithValue }) => {
    try {
      const { data } = await api.get('/reporting/dashboard/')
      return data
    } catch (err) {
      return rejectWithValue(
        err.response?.data?.detail ?? 'Erreur lors du chargement du reporting.'
      )
    }
  }
)

const reportingSlice = createSlice({
  name: 'reporting',
  initialState: {
    data: null,
    loading: false,
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchDashboard.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchDashboard.fulfilled, (state, action) => {
        state.data = action.payload
        state.loading = false
      })
      .addCase(fetchDashboard.rejected, (state, action) => {
        state.error = action.payload
        state.loading = false
      })
  },
})

export default reportingSlice.reducer
