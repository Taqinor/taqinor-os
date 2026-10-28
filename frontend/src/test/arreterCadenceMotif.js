import { expect } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'

/* CAD50 — parcours « Arrêter la cadence » commun au widget et à la page de
   suivi (ENF19) : le motif est exigé, `crmApi.arreterCadence(leadId, {motif})`
   est appelé, puis la saisie se referme sur succès. */
export async function arreterCadenceAvecMotif(crmApi, leadId) {
  fireEvent.click(screen.getByRole('button', { name: 'Arrêter la cadence' }))
  expect(screen.getByRole('button', { name: 'Confirmer' })).toBeDisabled()
  fireEvent.change(screen.getByTestId('cad50-arreter-motif'), { target: { value: 'Client injoignable' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
  await waitFor(() => expect(crmApi.arreterCadence).toHaveBeenCalledWith(leadId, { motif: 'Client injoignable' }))
  await waitFor(() => expect(screen.queryByTestId('cad50-arreter-motif')).not.toBeInTheDocument())
}
