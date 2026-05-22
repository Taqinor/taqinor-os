import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import parametresApi from '../../../api/parametresApi'

export const fetchProfile = createAsyncThunk('parametres/fetchProfile', async (_, { rejectWithValue }) => {
  try {
    const res = await parametresApi.getProfile()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const saveProfile = createAsyncThunk('parametres/saveProfile', async (data, { rejectWithValue }) => {
  try {
    const res = await parametresApi.updateProfile(data)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const uploadLogo = createAsyncThunk('parametres/uploadLogo', async (file, { rejectWithValue }) => {
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await parametresApi.uploadLogo(fd)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const deleteLogo = createAsyncThunk('parametres/deleteLogo', async (_, { rejectWithValue }) => {
  try {
    const res = await parametresApi.deleteLogo()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const uploadSignature = createAsyncThunk('parametres/uploadSignature', async (file, { rejectWithValue }) => {
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await parametresApi.uploadSignature(fd)
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

export const deleteSignature = createAsyncThunk('parametres/deleteSignature', async (_, { rejectWithValue }) => {
  try {
    const res = await parametresApi.deleteSignature()
    return res.data
  } catch (err) {
    return rejectWithValue(err.response?.data ?? err.message)
  }
})

const parametresSlice = createSlice({
  name: 'parametres',
  initialState: {
    profile: null,
    loading: false,
    saving: false,
    uploading: false,
    error: null,
    saveSuccess: false,
  },
  reducers: {
    clearSaveSuccess(state) { state.saveSuccess = false },
    clearError(state) { state.error = null },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchProfile.pending, (state) => { state.loading = true; state.error = null })
      .addCase(fetchProfile.fulfilled, (state, action) => {
        state.loading = false
        state.profile = action.payload
      })
      .addCase(fetchProfile.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })

      .addCase(saveProfile.pending, (state) => { state.saving = true; state.saveSuccess = false })
      .addCase(saveProfile.fulfilled, (state, action) => {
        state.saving = false
        state.saveSuccess = true
        state.profile = action.payload
      })
      .addCase(saveProfile.rejected, (state, action) => {
        state.saving = false
        state.error = action.payload
      })

      .addCase(uploadLogo.pending, (state) => { state.uploading = true })
      .addCase(uploadLogo.fulfilled, (state, action) => {
        state.uploading = false
        state.profile = action.payload
      })
      .addCase(uploadLogo.rejected, (state, action) => {
        state.uploading = false
        state.error = action.payload
      })

      .addCase(deleteLogo.fulfilled, (state, action) => { state.profile = action.payload })

      .addCase(uploadSignature.pending, (state) => { state.uploading = true })
      .addCase(uploadSignature.fulfilled, (state, action) => {
        state.uploading = false
        state.profile = action.payload
      })
      .addCase(uploadSignature.rejected, (state, action) => {
        state.uploading = false
        state.error = action.payload
      })

      .addCase(deleteSignature.fulfilled, (state, action) => { state.profile = action.payload })
  },
})

export const { clearSaveSuccess, clearError } = parametresSlice.actions
export default parametresSlice.reducer
