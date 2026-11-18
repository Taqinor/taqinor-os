import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import { renderAvecAuth } from '../../test/renderAvecAuth'

/* ADRG155 — la lecture des interventions récurrentes suit le droit de lecture
   du module chantiers (`installation_voir`) : un Commercial (ventes_voir seul)
   n'émet aucun GET (le serveur répondrait 403). */

const get = vi.fn(() => Promise.resolve({ data: { results: [
  { id: 1, type_intervention: 'nettoyage', regle: 'mensuelle', actif: true, prochaine_echeance: '2026-12-01' },
], next: null } }))
vi.mock('../../api/axios', () => ({ default: { get: (...a) => get(...a), post: vi.fn() } }))

import RecurrencesInterventionSection from './RecurrencesInterventionSection'

afterEach(() => { cleanup(); get.mockClear() })

const monter = (auth) => renderAvecAuth(
  <RecurrencesInterventionSection installationId={7} peutGerer />, { user: { id: 1 }, ...auth })

describe('RecurrencesInterventionSection — droit de lecture (ADRG155)', () => {
  it('Commercial : aucun GET des récurrences', async () => {
    monter({ role: 'commercial', role_nom: 'Commercial', permissions: ['ventes_voir', 'ventes_creer'] })
    await new Promise((r) => setTimeout(r, 30))
    expect(get).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Ajouter' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Nettoyage/)).not.toBeInTheDocument()
  })

  it('Technicien responsable : la liste est lue', async () => {
    monter({ role: 'responsable', role_nom: 'Technicien responsable',
      permissions: ['installation_voir', 'intervention_gerer'] })
    await waitFor(() => expect(screen.getByText(/Nettoyage/)).toBeInTheDocument())
    expect(get).toHaveBeenCalledTimes(1)
    expect(get.mock.calls[0][0]).toBe('/installations/recurrences-intervention/')
  })
})
