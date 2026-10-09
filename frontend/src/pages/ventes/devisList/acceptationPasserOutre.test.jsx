import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { screen, within, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* ADEV15 — modale « Accepter » : sur un 403 `sale_warning` / `credit_hold` le
   motif est affiché et un bouton « Passer outre » (Administrateur /
   Responsable seulement) renvoie la MÊME acceptation avec le drapeau.
   Réconcilié avec la décision fondateur 08/10/2026 : la fête part AU CLIC et
   la modale se ferme ; sur ce 403 la fête est retirée et la modale ROUVRE sur
   le même devis (saisie conservée) avec le motif + « Passer outre », dont le
   clic relance l'acceptation (et re-lance la fête à son clic). */

vi.mock('../../../ui/dealSignedBus', async (importOriginal) => {
  const m = await importOriginal()
  return {
    ...m,
    annoncerAffaireSignee: vi.fn(m.annoncerAffaireSignee),
    effacerAffaireSignee: vi.fn(m.effacerAffaireSignee),
  }
})

vi.mock('../../../features/ventes/store/ventesSlice', async (importOriginal) =>
  (await import('../../../test/devisListMocks.js')).ventesSliceMock(importOriginal))

vi.mock('../../../api/ventesApi', async (importOriginal) =>
  (await import('../../../test/devisListMocks.js')).ventesApiMock(importOriginal, {
    accepterDevis: vi.fn(),
  }))

vi.mock('../../../api/crmApi', async (importOriginal) =>
  (await import('../../../test/devisListMocks.js')).crmApiMotifsMock(importOriginal))

vi.mock('../../../api/uxviewsApi', async () =>
  (await import('../../../test/devisListMocks.js')).uxviewsApiMock())

import DevisList from '../DevisList'
import ventesApi from '../../../api/ventesApi'
import { renderListeVentes } from '../../../test/devisListRender.jsx'
import { annoncerAffaireSignee, effacerAffaireSignee } from '../../../ui/dealSignedBus'

const DEVIS = [{
  id: 515, reference: 'DEV-A15', client_nom: 'ACME', statut: 'envoye',
  date_creation: '2026-07-01', total_ttc: 5000, nb_options: 1, version: 1,
  is_active: true, mode_installation: 'residentiel',
}]

function ouvrir(role) {
  renderListeVentes(DevisList, {
    devis: DEVIS,
    auth: { role, role_nom: role, permissions: ['ventes_valider'] },
  })
  const row = screen.getByText('DEV-A15').closest('tr')
  fireEvent.click(within(row).getByRole('button', { name: /Accepter/ }))
}

const refus403 = (corps) => Object.assign(new Error('403'), {
  response: { status: 403, data: corps },
})

beforeEach(() => {
  ventesApi.accepterDevis.mockReset()
  annoncerAffaireSignee.mockClear()
  effacerAffaireSignee.mockClear()
})
afterEach(() => { cleanup() })

describe('ADEV15 — « Passer outre » à l\'acceptation', () => {
  it('admin : 403 sale_warning → motif + Passer outre → renvoie override_avertissement', async () => {
    const user = userEvent.setup()
    ventesApi.accepterDevis
      .mockRejectedValueOnce(refus403({
        detail: 'Avertissement de vente bloquant : client litigieux.', sale_warning: true,
      }))
      .mockResolvedValueOnce({ data: { statut: 'accepte' } })
    ouvrir('admin')
    await user.type(await screen.findByLabelText('Nom de la personne qui accepte'), 'Sami')
    await user.click(screen.getByRole('button', { name: /Confirmer l'acceptation/ }))
    // Fête lancée AU CLIC, puis retirée au 403 ; la modale rouvre avec le motif.
    expect(annoncerAffaireSignee).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/client litigieux/)).toBeTruthy()
    expect(effacerAffaireSignee).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('Nom de la personne qui accepte').value).toBe('Sami')
    await user.click(screen.getByRole('button', { name: /Passer outre/ }))
    await waitFor(() => expect(ventesApi.accepterDevis).toHaveBeenCalledTimes(2))
    // « Passer outre » re-lance la fête à son clic ; succès → pas d'effacement.
    expect(annoncerAffaireSignee).toHaveBeenCalledTimes(2)
    await waitFor(() => expect(screen.queryByText(/client litigieux/)).toBeNull())
    expect(effacerAffaireSignee).toHaveBeenCalledTimes(1)
    const [id, corps] = ventesApi.accepterDevis.mock.calls[1]
    expect(id).toBe(515)
    expect(corps.override_avertissement).toBe(true)
    expect(corps.override_credit).toBeUndefined()
    expect(corps.nom).toBe('Sami')
    expect(ventesApi.accepterDevis.mock.calls[0][1].override_avertissement).toBeUndefined()
  })

  it('admin : 403 credit_hold → renvoie override_credit', async () => {
    const user = userEvent.setup()
    ventesApi.accepterDevis
      .mockRejectedValueOnce(refus403({ detail: 'Client en blocage crédit.', credit_hold: true }))
      .mockResolvedValueOnce({ data: {} })
    ouvrir('admin')
    await user.type(await screen.findByLabelText('Nom de la personne qui accepte'), 'Sami')
    await user.click(screen.getByRole('button', { name: /Confirmer l'acceptation/ }))
    await user.click(await screen.findByRole('button', { name: /Passer outre/ }))
    await waitFor(() => expect(ventesApi.accepterDevis).toHaveBeenCalledTimes(2))
    expect(ventesApi.accepterDevis.mock.calls[1][1].override_credit).toBe(true)
  })

  it('commercial : le motif est affiché mais aucun bouton Passer outre', async () => {
    const user = userEvent.setup()
    ventesApi.accepterDevis.mockRejectedValueOnce(refus403({
      detail: 'Avertissement de vente bloquant : client litigieux.', sale_warning: true,
    }))
    ouvrir('commercial')
    await user.type(await screen.findByLabelText('Nom de la personne qui accepte'), 'Sami')
    await user.click(screen.getByRole('button', { name: /Confirmer l'acceptation/ }))
    expect(await screen.findByText(/client litigieux/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Passer outre/ })).toBeNull()
  })
})
