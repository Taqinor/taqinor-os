import { configureStore, combineReducers } from '@reduxjs/toolkit'
import authReducer from '../features/auth/store/authSlice'
import stockReducer from '../features/stock/store/stockSlice'
import crmReducer from '../features/crm/store/crmSlice'
import ventesReducer from '../features/ventes/store/ventesSlice'
import iaReducer from '../features/ia/store/iaSlice'
import parametresReducer from '../features/parametres/store/parametresSlice'
import reportingReducer from '../features/reporting/store/reportingSlice'
import installationsReducer from '../features/installations/store/installationsSlice'

const appReducer = combineReducers({
  auth: authReducer,
  stock: stockReducer,
  crm: crmReducer,
  ventes: ventesReducer,
  ia: iaReducer,
  parametres: parametresReducer,
  reporting: reportingReducer,
  installations: installationsReducer,
})

// Reset all slices to their initial state on logout so no data leaks between users
const rootReducer = (state, action) => {
  if (action.type === 'auth/logout') {
    localStorage.clear()
    return appReducer(undefined, action)
  }
  return appReducer(state, action)
}

export const store = configureStore({
  reducer: rootReducer,
})

export default store
