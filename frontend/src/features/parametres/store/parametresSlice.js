import { createSlice, createAsyncThunk, isAnyOf } from '@reduxjs/toolkit'
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
    // APAR73 — horodatage du verrou optimiste (`updated_at` du profil), rangé
    // à part : une écriture instantanée le fait avancer SANS toucher `profile`
    // (donc sans resynchroniser le formulaire en cours de saisie).
    verrouUpdatedAt: null,
  },
  reducers: {
    clearSaveSuccess(state) { state.saveSuccess = false },
    clearError(state) { state.error = null },
    majVerrouProfil(state, action) {
      if (action.payload) state.verrouUpdatedAt = action.payload
    },
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

      // APAR42 — une nouvelle tentative / un succès ACQUITTE l'erreur
      // précédente : l'ancien bandeau rouge ne revient plus après « Profil
      // enregistré ».
      .addCase(saveProfile.pending, (state) => {
        state.saving = true
        state.saveSuccess = false
        state.error = null
      })
      .addCase(saveProfile.fulfilled, (state, action) => {
        state.saving = false
        state.saveSuccess = true
        state.error = null
        state.profile = action.payload
      })
      .addCase(saveProfile.rejected, (state, action) => {
        state.saving = false
        state.error = action.payload
      })

      .addCase(uploadLogo.pending, (state) => { state.uploading = true; state.error = null })
      .addCase(uploadLogo.fulfilled, (state, action) => {
        state.uploading = false
        state.error = null
        state.profile = action.payload
      })
      .addCase(uploadLogo.rejected, (state, action) => {
        state.uploading = false
        state.error = action.payload
      })

      .addCase(deleteLogo.fulfilled, (state, action) => { state.profile = action.payload; state.error = null })

      .addCase(uploadSignature.pending, (state) => { state.uploading = true; state.error = null })
      .addCase(uploadSignature.fulfilled, (state, action) => {
        state.uploading = false
        state.error = null
        state.profile = action.payload
      })
      .addCase(uploadSignature.rejected, (state, action) => {
        state.uploading = false
        state.error = action.payload
      })

      .addCase(deleteSignature.fulfilled, (state, action) => { state.profile = action.payload; state.error = null })

      // APAR73 — toute réponse qui rend le profil complet repose le verrou.
      .addMatcher(
        isAnyOf(fetchProfile.fulfilled, saveProfile.fulfilled, uploadLogo.fulfilled,
          deleteLogo.fulfilled, uploadSignature.fulfilled, deleteSignature.fulfilled),
        (state, action) => { state.verrouUpdatedAt = action.payload?.updated_at ?? null },
      )
  },
})

export const { clearSaveSuccess, clearError, majVerrouProfil } = parametresSlice.actions
export default parametresSlice.reducer
