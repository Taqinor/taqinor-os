import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../api/recordsApi', () => ({
  default: {
    getActivities: vi.fn(),
    getActivityTypes: vi.fn(() => Promise.resolve({ data: [] })),
    createActivity: vi.fn(),
    updateActivity: vi.fn(),
    deleteActivity: vi.fn(),
    markActivityDone: vi.fn(),
  },
}))

import recordsApi from '../api/recordsApi'
import ActivitiesPanel from './ActivitiesPanel'
import { ConfirmProvider } from '../providers/ConfirmProvider'

/* VX204 — `load()` avalait ses échecs (`.catch(() => {})`) : l'état `error`
   existait déjà (ligne 26) mais n'était jamais alimenté, rendant un échec de
   chargement INDISCERNABLE de « aucune relance due ». */
describe('ActivitiesPanel (VX204)', () => {
  it('un échec de chargement affiche un message + Réessayer, jamais le vide muet', async () => {
    recordsApi.getActivities.mockRejectedValueOnce(new Error('boom'))
    render(<ActivitiesPanel model="crm.lead" id={1} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Impossible de charger les activités.')
    expect(screen.queryByText('Aucune activité planifiée.')).not.toBeInTheDocument()
  })

  it('Réessayer relance le chargement et efface l\'erreur en cas de succès', async () => {
    recordsApi.getActivities.mockRejectedValueOnce(new Error('boom'))
    render(<ActivitiesPanel model="crm.lead" id={1} />)
    await screen.findByRole('alert')

    recordsApi.getActivities.mockResolvedValueOnce({ data: [] })
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
    expect(await screen.findByText('Aucune activité planifiée.')).toBeInTheDocument()
  })

  it('un chargement réussi sans activité affiche le vide normal (pas d\'erreur)', async () => {
    recordsApi.getActivities.mockResolvedValueOnce({ data: [] })
    render(<ActivitiesPanel model="crm.lead" id={1} />)
    expect(await screen.findByText('Aucune activité planifiée.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('ActivitiesPanel (AERR68)', () => {
  it('Supprimer puis Annuler : aucune suppression, la boîte nomme l’activité', async () => {
    recordsApi.deleteActivity.mockClear()
    recordsApi.getActivities.mockResolvedValueOnce({ data: [
      { id: 5, done: false, state: 'planned', activity_type_nom: 'Appel', summary: 'Rappeler Karim' },
    ] })
    render(<ConfirmProvider><ActivitiesPanel model="crm.lead" id={1} /></ConfirmProvider>)
    fireEvent.click(await screen.findByTitle('Supprimer'))
    expect(await screen.findByText(/Appel — Rappeler Karim sera supprimée/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByText('Supprimer cette activité ?')).not.toBeInTheDocument())
    expect(recordsApi.deleteActivity).not.toHaveBeenCalled()
  })
})
