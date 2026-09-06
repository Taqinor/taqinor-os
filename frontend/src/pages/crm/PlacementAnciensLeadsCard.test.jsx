import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'

/* MRY33 — carte Cockpit « Anciens leads à placer dans les cadences ». Charge
   utile venant de l'exemple COMMITTÉ
   (`apps/crm/contract_samples/placement_anciens_leads.json`, PACT10), jamais
   un objet retapé à la main : c'est cette deuxième source de vérité qui
   avait laissé passer l'écran AO mort du 03/08/2026 (test vert, écran mort).
   Si le serveur change de forme, l'exemple change et ce test casse tout
   seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const DONNEES = exempleContrat('crm', 'placement_anciens_leads')

// Même patron que `IdentityRail.test.jsx` : le hook de rôle est mocké plutôt
// qu'un vrai Provider redux — réassignable par test.
const isAdminOrResponsableMock = vi.fn(() => true)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    placerAnciensLeads: vi.fn(),
  },
}))

// Même patron que `ClientForm.test.jsx` : confirmation/toast mockés (le
// composant réel `ui/confirm` n'est pas ce qu'on vérifie ici).
const confirmMock = vi.fn(() => Promise.resolve(true))
vi.mock('../../ui/confirm', () => ({
  useConfirmDialog: () => ({ confirm: (...args) => confirmMock(...args), confirmDelete: vi.fn() }),
  toast: { success: vi.fn(), error: vi.fn() },
}))

import crmApi from '../../api/crmApi'
import { toast } from '../../ui/confirm'
import PlacementAnciensLeadsCard from './PlacementAnciensLeadsCard'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(true)
  confirmMock.mockResolvedValue(true)
  crmApi.placerAnciensLeads.mockResolvedValue(reponseContrat('crm', 'placement_anciens_leads'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlacementAnciensLeadsCard (MRY33)', () => {
  it('masquée pour un rôle normal (aucun appel réseau)', () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    const { container } = render(<PlacementAnciensLeadsCard />)
    expect(container).toBeEmptyDOMElement()
    expect(crmApi.placerAnciensLeads).not.toHaveBeenCalled()
  })

  it('« Aperçu » affiche les cinq lignes par étape et le total à placer', async () => {
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(crmApi.placerAnciensLeads).toHaveBeenCalledWith({ apply: false }))
    await waitFor(() => {
      for (const etape of DONNEES.par_etape) {
        expect(screen.getByText(etape.libelle)).toBeInTheDocument()
      }
    })
    expect(screen.getAllByText(new RegExp(String(DONNEES.a_placer))).length).toBeGreaterThan(0)
    expect(screen.getAllByText(new RegExp(String(DONNEES.total_candidats))).length).toBeGreaterThan(0)
    // Le premier lead de l'aperçu (contrat) est bien listé.
    expect(screen.getByText(DONNEES.apercu[0].nom)).toBeInTheDocument()
  })

  it('« Appliquer » est désactivé avant tout aperçu, puis ouvre la confirmation et appelle l\'API avec apply=true', async () => {
    render(<PlacementAnciensLeadsCard />)
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()

    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())

    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    // N = a_placer, M = somme des codes dormant_* (150 + 58 = 208 sur le contrat).
    const [options] = confirmMock.mock.calls[0]
    expect(options.description).toContain(String(DONNEES.a_placer))
    expect(options.description).toContain('208')

    await waitFor(() => expect(crmApi.placerAnciensLeads).toHaveBeenCalledWith({ apply: true }))
    await waitFor(() => expect(toast.success).toHaveBeenCalled())
  })

  it('Annuler la confirmation n\'appelle jamais l\'API avec apply=true', async () => {
    confirmMock.mockResolvedValueOnce(false)
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Appliquer' })).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(confirmMock).toHaveBeenCalled())
    expect(crmApi.placerAnciensLeads).not.toHaveBeenCalledWith({ apply: true })
  })

  it('aucun ancien lead à placer : message et repli, la carte se replie', async () => {
    crmApi.placerAnciensLeads.mockResolvedValue(
      reponseContrat('crm', 'placement_anciens_leads', 'exemple_vide'))
    render(<PlacementAnciensLeadsCard />)
    fireEvent.click(screen.getByRole('button', { name: 'Aperçu' }))
    expect(await screen.findByText(/Aucun ancien lead à placer/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Appliquer' })).toBeDisabled()
  })
})
