import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../../../api/axios'
// VX162 — logout propagé à tous les onglets (poste partagé).
// LW45 — logout local (cet onglet) : purge les caches best-effort (ex. leadPrefetch.js).
import { broadcastLogout, emitAuthLogout } from '../../../providers/session-bridge'

// Recupere les infos utilisateur depuis l'API (cookie envoye automatiquement)
export const fetchMe = createAsyncThunk(
  'auth/fetchMe',
  async (_, { rejectWithValue }) => {
    try {
      // J3 — serveur chargé (42 s mesurés le 22/11) : le démarrage attend 60 s au lieu de 20 s,
      // et l'écran de démarrage dit lui-même qu'il attend (aucun toast d'expiration).
      const { data } = await api.get('/auth/me/', { silencieuxExpiration: true, timeout: 60000 })
      return data
    } catch (err) {
      // ADEP33 — le rejet DISTINGUE un refus d'authentification (401/403) d'une
      // panne : ``reseau`` = aucune réponse reçue (hors ligne, DNS, timeout),
      // ``status`` = code HTTP reçu (null sans réponse). Contrat interne front
      // consommé par le routeur (ADEP19). J3 : ``expire`` = le délai du client
      // est dépassé (le serveur est lent, pas injoignable).
      const status = err?.response?.status ?? null
      const expire = err?.code === 'ECONNABORTED' || err?.code === 'ETIMEDOUT'
      return rejectWithValue({ status, reseau: !err?.response, expire })
    }
  }
)

// Décision fondateur 12/11/2026 (remplace APAR57) : se déconnecter NE coupe
// PLUS les notifications push de l'appareil — elles continuent tant que
// l'appareil reste abonné. On ne les coupe que par l'interrupteur de
// Paramètres → Notifications. Un autre utilisateur qui se connecte sur le
// même appareil reprend l'abonnement à son nom (réabonnement à la connexion,
// `reabonnerPushSiAutorise`), jamais les deux à la fois.
export const logoutUser = createAsyncThunk(
  'auth/logoutUser',
  async (_, { dispatch }) => {
    try {
      // Le cookie refresh_token est envoye automatiquement
      await api.post('/auth/logout/', {})
    } catch {
      console.warn('authSlice (auth/logoutUser) : Continuer meme si le serveur echoue')
    }
    dispatch(authSlice.actions.logout())
    // LW45 — purge les caches best-effort de CET onglet (ex. leadPrefetch.js).
    emitAuthLogout()
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
    // ADEP33 — vrai quand /auth/me/ n'a PAS pu trancher (panne réseau, 5xx) :
    // la session courante est conservée, ni confirmée ni révoquée.
    sessionInconnue: false,
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
      state.sessionInconnue = false
      state.loading = false
    },
    logout: (state) => {
      state.user = null
      state.role = null
      state.role_nom = null
      state.permissions = []
      state.modulesDesactives = []
      state.isAuthenticated = false
      state.sessionInconnue = false
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
        state.sessionInconnue = false
        state.loading = false
      })
      .addCase(fetchMe.rejected, (state, action) => {
        state.loading = false
        const status = action.payload?.status
        if (status === 401 || status === 403) {
          // Refus d'authentification : pas de session valide (comme avant).
          state.isAuthenticated = false
          state.sessionInconnue = false
          return
        }
        // ADEP33 — panne (pas de réponse, 5xx, autre) : le serveur n'a PAS dit
        // « non authentifié ». On ne déconnecte pas : la session (et le profil)
        // courants sont conservés tels quels — un démarrage à froid reste donc
        // non authentifié (état initial), aucune session n'est jamais créée ici.
        state.sessionInconnue = true
      })
  },
})

export const { setCredentials, logout } = authSlice.actions

export const hasPermission = (code) => (state) =>
  state.auth.permissions.includes(code)

export default authSlice.reducer
