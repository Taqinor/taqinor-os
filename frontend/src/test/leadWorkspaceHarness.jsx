import './leadWorkspaceMocks'
import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../features/crm/store/crmSlice'
import LeadWorkspace from '../features/crm/workspace/LeadWorkspace'

/* Rendu COMMUN des suites LeadWorkspace (ENF19) : store Redux minimal
   (utilisateur connecté) + routeur mémoire autour du vrai `LeadWorkspace`.
   Importe `leadWorkspaceMocks` d'abord, donc les neutralisations communes sont
   enregistrées avant le chargement du composant. */
export function makeStore(userId = 42) {
  return configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: userId } }) => s } })
}

/** Monte `LeadWorkspace` (onClose/onSaved neutres, surchargeables via `props`). */
export function renderLeadWorkspace(props = {}, userId = 42) {
  return render(
    <Provider store={makeStore(userId)}>
      <MemoryRouter>
        <LeadWorkspace onClose={vi.fn()} onSaved={vi.fn()} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}
