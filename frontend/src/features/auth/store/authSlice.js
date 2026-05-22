import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../../../api/axios'

function decodeToken(token) {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

const savedToken = sessionStorage.getItem('token')
const savedPayload = savedToken ? decodeToken(savedToken) : null

const initialState = {
  user: savedPayload ? { username: savedPayload.username } : null,
  role: savedPayload?.role || null,
  role_nom: savedPayload?.role_nom || null,
  permissions: savedPayload?.permissions || [],
  token: savedToken,
  isAuthenticated: !!savedToken,
}

export const fetchMe = createAsyncThunk(
  'auth/fetchMe',
  async (_, { rejectWithValue }) => {
    try {
      const { data } = await api.get('/auth/me/')
      return data
    } catch (err) {
      return rejectWithValue(err.response?.data)
    }
  }
)

export const logoutUser = createAsyncThunk(
  'auth/logoutUser',
  async (_, { dispatch }) => {
    const refresh = sessionStorage.getItem('refresh')
    if (refresh) {
      try {
        await api.post('/auth/logout/', { refresh })
      } catch {
        // token already expired — proceed anyway
      }
    }
    dispatch(authSlice.actions.logout())
  }
)

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setCredentials: (state, action) => {
      const payload = decodeToken(action.payload.token)
      state.user = action.payload.user
      state.role = payload?.role || 'normal'
      state.role_nom = payload?.role_nom || null
      state.permissions = payload?.permissions || []
      state.token = action.payload.token
      state.isAuthenticated = true
      sessionStorage.setItem('token', action.payload.token)
    },
    logout: (state) => {
      state.user = null
      state.role = null
      state.role_nom = null
      state.permissions = []
      state.token = null
      state.isAuthenticated = false
      sessionStorage.removeItem('token')
      sessionStorage.removeItem('refresh')
    },
  },
  extraReducers: (builder) => {
    builder.addCase(fetchMe.fulfilled, (state, action) => {
      state.user = { username: action.payload.username }
      state.role = action.payload.role_legacy || action.payload.role || 'normal'
      state.role_nom = action.payload.role_nom || null
      state.permissions = action.payload.permissions || []
    })
  },
})

export const { setCredentials, logout } = authSlice.actions

/**
 * Selector: check if the current user has a specific ERP permission.
 * Usage: useSelector(hasPermission('stock_voir'))
 */
export const hasPermission = (code) => (state) =>
  state.auth.permissions.includes(code)

export default authSlice.reducer
