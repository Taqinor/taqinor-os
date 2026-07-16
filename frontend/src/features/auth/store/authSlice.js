import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../../../api/axios'
// VX162 — logout propagé à tous les onglets (poste partagé).
import { broadcastLogout } from '../../../providers/session-bridge'

// Recupere les infos utilisateur depuis l'API (cookie envoye automatiquement)
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
    try {
      // Le cookie refresh_token est envoye automatiquement
      await api.post('/auth/logout/', {})
    } catch {
      // Continuer meme si le serveur echoue
    }
    dispatch(authSlice.actions.logout())
    // VX162 — publie le logout aux AUTRES onglets (poste partagé) : ils se
    // déconnectent localement sans attendre leur premier 401.
    broadcastLogout()
  }
)

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    role: null,
    role_nom: null,
    permissions: [],
    // ODX6 — clés des modules DÉSACTIVÉS pour la société de l'utilisateur,
    // servies par /auth/me/. Défaut = [] ⇒ nav strictement identique à
    // aujourd'hui (aucun module masqué tant qu'aucun toggle n'existe).
    modulesDesactives: [],
    isAuthenticated: false,
    loading: true, // true au demarrage : on verifie la session
  },
  reducers: {
    setCredentials: (state, action) => {
      state.user = action.payload.user
      // Palier de menu : on privilégie le signal dérivé du NOUVEAU rôle.
      state.role = action.payload.menu_tier || action.payload.role || 'normal'
      state.role_nom = action.payload.role_nom || null
      state.permissions = action.payload.permissions || []
      state.modulesDesactives = action.payload.modules_desactives || []
      state.isAuthenticated = true
      state.loading = false
    },
    logout: (state) => {
      state.user = null
      state.role = null
      state.role_nom = null
      state.permissions = []
      state.modulesDesactives = []
      state.isAuthenticated = false
      state.loading = false
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchMe.pending, (state) => {
        state.loading = true
      })
      .addCase(fetchMe.fulfilled, (state, action) => {
        // On conserve l'objet utilisateur COMPLET (email + autres champs), comme
        // le fait le chemin de login — sinon la ligne email de l'en-tête et les
        // autres consommateurs reçoivent `undefined` après un rechargement.
        state.user = action.payload
        // menu_tier (dérivé du nouveau rôle) fait autorité ; repli sur le legacy
        // uniquement pour les comptes sans rôle.
        state.role = action.payload.menu_tier || action.payload.role_legacy || action.payload.role || 'normal'
        state.role_nom = action.payload.role_nom || null
        state.permissions = action.payload.permissions || []
        state.modulesDesactives = action.payload.modules_desactives || []
        state.isAuthenticated = true
        state.loading = false
      })
      .addCase(fetchMe.rejected, (state) => {
        // Pas de session valide
        state.isAuthenticated = false
        state.loading = false
      })
  },
})

export const { setCredentials, logout } = authSlice.actions

export const hasPermission = (code) => (state) =>
  state.auth.permissions.includes(code)

export default authSlice.reducer
