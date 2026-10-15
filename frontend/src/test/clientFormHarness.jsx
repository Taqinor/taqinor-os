import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import crmReducer from '../features/crm/store/crmSlice'
import ClientForm from '../pages/crm/ClientForm'

/* Rendu COMMUN des suites ClientForm : store Redux CRM minimal + vrai formulaire. */
export const renderClientForm = (props = {}) => {
  const store = configureStore({ reducer: { crm: crmReducer } })
  return render(
    <Provider store={store}>
      <ClientForm onClose={vi.fn()} {...props} />
    </Provider>,
  )
}
