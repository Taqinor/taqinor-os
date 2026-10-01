// QJR589 (contrat QJR505 `devis_reappliquer_lead.json`) — la bannière de
// dérive lead → devis : libellés français, deux gestes qui la résolvent, et
// « Réviser » seulement sur un devis figé. La réponse simulée est l'exemple
// COMMITTÉ du contrat (PACT10).
//
// Run : npx vitest run src/features/ventes/quote/BandeauDeriveLead.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/ventesApi', () => ({
  default: {
    reappliquerLeadDevis: vi.fn(),
    acquitterDeriveDevis: vi.fn(),
  },
}))

import ventesApi from '../../../api/ventesApi'
import BandeauDeriveLead from './BandeauDeriveLead'

const REPRIS = exempleContrat('ventes', 'devis_reappliquer_lead')
const GARDE = exempleContrat('ventes', 'devis_reappliquer_lead', 'exemple_garder')

beforeEach(() => {
  vi.clearAllMocks()
  ventesApi.reappliquerLeadDevis.mockResolvedValue({ data: REPRIS })
  ventesApi.acquitterDeriveDevis.mockResolvedValue({ data: GARDE })
})

describe('QJR589 — bannière de dérive lead → devis', () => {
  it('nomme les champs en français et propose les deux gestes', () => {
    render(<BandeauDeriveLead devisId={413} statut="brouillon"
                              champs={['facture_hiver', 'ville_reference']} />)
    const bandeau = screen.getByTestId('lead-valeurs-modifiees')
    expect(bandeau.textContent).toMatch(/facture d’hiver, ville de rattachement/)
    expect(screen.getByRole('button', { name: 'Reprendre les valeurs du lead' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Garder les valeurs du devis' })).toBeTruthy()
  })

  it('« Reprendre » appelle reappliquer-lead puis masque la bannière', async () => {
    const onResolu = vi.fn()
    render(<BandeauDeriveLead devisId={413} statut="envoye" champs={['facture_hiver']}
                              onResolu={onResolu} />)
    expect(screen.getByTestId('lead-valeurs-modifiees').textContent)
      .toMatch(/le client verra la version corrigée/)
    await userEvent.click(screen.getByRole('button', { name: 'Reprendre les valeurs du lead' }))
    await waitFor(() => expect(ventesApi.reappliquerLeadDevis).toHaveBeenCalledWith(413))
    expect(onResolu).toHaveBeenCalledWith(REPRIS)
    expect(screen.queryByTestId('lead-valeurs-modifiees')).toBeNull()
    expect(ventesApi.acquitterDeriveDevis).not.toHaveBeenCalled()
  })

  it('« Garder » appelle acquitter-derive', async () => {
    render(<BandeauDeriveLead devisId={413} statut="brouillon" champs={['facture_hiver']} />)
    await userEvent.click(screen.getByRole('button', { name: 'Garder les valeurs du devis' }))
    await waitFor(() => expect(ventesApi.acquitterDeriveDevis).toHaveBeenCalledWith(413))
    expect(screen.queryByTestId('lead-valeurs-modifiees')).toBeNull()
  })

  it('accepté : lien « Réviser », aucun des deux gestes', async () => {
    const onReviser = vi.fn()
    render(<BandeauDeriveLead devisId={414} statut="accepte" champs={['facture_hiver']}
                              onReviser={onReviser} />)
    expect(screen.queryByRole('button', { name: /Reprendre les valeurs du lead/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Garder les valeurs du devis/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Réviser' }))
    expect(onReviser).toHaveBeenCalled()
  })

  it('un échec serveur est dit, la bannière reste', async () => {
    ventesApi.reappliquerLeadDevis.mockRejectedValue({
      response: { status: 400, data: exempleContrat('ventes', 'devis_reappliquer_lead', 'exemple_400') },
    })
    render(<BandeauDeriveLead devisId={413} statut="brouillon" champs={['facture_hiver']} />)
    await userEvent.click(screen.getByRole('button', { name: 'Reprendre les valeurs du lead' }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByTestId('lead-valeurs-modifiees')).toBeTruthy()
  })

  it('aucune dérive → rien', () => {
    const { container } = render(<BandeauDeriveLead devisId={413} statut="brouillon" champs={[]} />)
    expect(container.textContent).toBe('')
  })
})
