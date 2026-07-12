import { configureStore, combineReducers } from '@reduxjs/toolkit'
import authReducer from '../features/auth/store/authSlice'
import stockReducer from '../features/stock/store/stockSlice'
import crmReducer from '../features/crm/store/crmSlice'
import ventesReducer from '../features/ventes/store/ventesSlice'
import iaReducer from '../features/ia/store/iaSlice'
import parametresReducer from '../features/parametres/store/parametresSlice'
import reportingReducer from '../features/reporting/store/reportingSlice'
import installationsReducer from '../features/installations/store/installationsSlice'
import equipementsReducer from '../features/sav/store/equipementsSlice'
import ticketsReducer from '../features/sav/store/ticketsSlice'
import messagingReducer from '../features/messaging/store/messagingSlice'

const appReducer = combineReducers({
  auth: authReducer,
  stock: stockReducer,
  crm: crmReducer,
  ventes: ventesReducer,
  ia: iaReducer,
  parametres: parametresReducer,
  reporting: reportingReducer,
  installations: installationsReducer,
  equipements: equipementsReducer,
  tickets: ticketsReducer,
  messaging: messagingReducer,
})

// Clés localStorage strictement liées à l'authentification à purger au logout.
// L'auth est basée sur des cookies httpOnly : aucun token n'est stocké côté
// client, donc cette liste est vide aujourd'hui. On purge UNIQUEMENT ces clés
// — surtout PAS `localStorage.clear()`, qui effacerait le thème, l'état de la
// sidebar, les vues/filtres de leads enregistrés et les drapeaux PWA.
const AUTH_LOCALSTORAGE_KEYS = []

// Reset all slices to their initial state on logout so no data leaks between users
const rootReducer = (state, action) => {
  if (action.type === 'auth/logout') {
    AUTH_LOCALSTORAGE_KEYS.forEach((key) => {
      try { localStorage.removeItem(key) } catch { /* stockage indisponible */ }
    })
    return appReducer(undefined, action)
  }
  return appReducer(state, action)
}

export const store = configureStore({
  reducer: rootReducer,
  // VX201 — en prod, l'extension Redux DevTools expose TOUT le state (PII,
  // matrice de permissions, leads/devis/factures) : coupée hors dev.
  devTools: import.meta.env.DEV,
})

export default store
