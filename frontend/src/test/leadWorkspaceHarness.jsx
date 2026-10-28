import './leadWorkspaceMocks'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, expect } from 'vitest'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../features/crm/store/crmSlice'
import crmApi from '../api/crmApi'
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

/** Autosave en échec RÉSEAU (503) sur « ville » d'un lead ouvert : attend le GET
    d'ouverture, tape, puis l'affordance « Réessayer » (brouillon intact). */
export async function echecReseauAutosaveVille(lead) {
  crmApi.updateLead.mockRejectedValueOnce({ response: { status: 503 } })
  renderLeadWorkspace({ lead })
  await waitFor(() => expect(crmApi.getLead).toHaveBeenCalled())
  fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })
  await waitFor(
    () => expect(screen.getByRole('button', { name: /Réessayer/ })).toBeInTheDocument(),
    { timeout: 3000 },
  )
}
