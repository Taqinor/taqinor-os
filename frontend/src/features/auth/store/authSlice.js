import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../../../api/axios'
// VX162 — logout propagé à tous les onglets (poste partagé).
// LW45 — logout local (cet onglet) : purge les caches best-effort (ex. leadPrefetch.js).
import { broadcastLogout, emitAuthLogout } from '../../../providers/session-bridge'
// APAR57 — désabonnement push de l'appareil à la déconnexion.
import { pushSupported, unsubscribeFromPush } from '../../pwa/pushSubscribe'

// Recupere les infos utilisateur depuis l'API (cookie envoye automatiquement)
export const fetchMe = createAsyncThunk(
  'auth/fetchMe',
  async (_, { rejectWithValue }) => {
    try {
      const { data } = await api.get('/auth/me/')
      return data
    } catch (err) {
      // ADEP33 — le rejet DISTINGUE un refus d'authentification (401/403) d'une
      // panne : ``reseau`` = aucune réponse reçue (hors ligne, DNS, timeout),
      // ``status`` = code HTTP reçu (null sans réponse). Contrat interne front
      // consommé par le routeur (ADEP19).
      const status = err?.response?.status ?? null
      return rejectWithValue({ status, reseau: !err?.response })
    }
  }
)

// APAR57 — borne une étape push best-effort : un service worker absent ou
// bloqué ne doit JAMAIS retenir la déconnexion.
const PUSH_DELAI_MS = 2000
function avecDelai(promise, ms, defaut) {
  let timer
  const garde = new Promise((resolve) => { timer = setTimeout(() => resolve(defaut), ms) })
  return Promise.race([promise, garde]).finally(() => clearTimeout(timer))
}

// APAR57 — désabonne CET appareil du push AVANT /auth/logout/ (poste partagé :
// plus aucun push porteur de jetons « Approuver/Refuser » vers ce navigateur).
// Rend l'endpoint désabonné (transmis au serveur, qui supprime la ligne) ou null.
async function desabonnerPushAvantLogout() {
  if (!pushSupported()) return null
  try {
    const sw = navigator.serviceWorker
    const reg = await avecDelai(
      sw.getRegistration ? sw.getRegistration() : sw.ready, PUSH_DELAI_MS, null,
    )
    if (!reg || !reg.pushManager) return null
    const sub = await avecDelai(reg.pushManager.getSubscription(), PUSH_DELAI_MS, null)
    if (!sub) return null
    const endpoint = sub.endpoint || null
    await avecDelai(unsubscribeFromPush(), PUSH_DELAI_MS, null)
    return endpoint
  } catch {
    return null
  }
}

export const logoutUser = createAsyncThunk(
  'auth/logoutUser',
  async (_, { dispatch }) => {
    const pushEndpoint = await desabonnerPushAvantLogout()
    try {
      // Le cookie refresh_token est envoye automatiquement
      await api.post('/auth/logout/', pushEndpoint ? { push_endpoint: pushEndpoint } : {})
    } catch {
      // Continuer meme si le serveur echoue
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
