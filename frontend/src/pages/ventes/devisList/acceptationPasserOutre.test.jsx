/* global process */
import { describe, it, expect, vi, afterEach, beforeEach, beforeAll, afterAll } from 'vitest'
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
import { documentContrat } from '../../../test/fixtures/contractSamples'
import { toast } from '../../../ui'

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

// VNT80 — un 409 qui NOMME un autre devis (`vente_active_existante.vente_active`,
// exemple committé devis_prix_negocie.json) : la fête est retirée, le message
// s'affiche SOUS la ligne et « Ouvrir <réf> » surligne ce devis (?devis=<id>).
describe('VNT80 — acceptation refusée : vente active existante', () => {
  it('message sous la ligne + « Ouvrir » défile jusqu’au devis nommé', async () => {
    const refus = documentContrat('ventes', 'devis_prix_negocie').erreurs_409.vente_active_existante
    const cible = refus.vente_active
    ventesApi.accepterDevis.mockRejectedValueOnce(Object.assign(new Error('409'), {
      response: { status: 409, data: refus },
    }))
    const defile = vi.spyOn(window.HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => {})
    const user = userEvent.setup()
    renderListeVentes(DevisList, {
      devis: [...DEVIS, { ...DEVIS[0], id: cible.id, reference: cible.reference, statut: 'accepte' }],
      auth: { role: 'admin', role_nom: 'admin', permissions: ['ventes_valider'] },
    })
    const row = screen.getByText('DEV-A15').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: /Accepter/ }))
    await user.type(await screen.findByLabelText('Nom de la personne qui accepte'), 'Sami')
    await user.click(screen.getByRole('button', { name: /Confirmer l'acceptation/ }))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(refus.detail)
    expect(effacerAffaireSignee).toHaveBeenCalledTimes(1)
    await user.click(within(alerte).getByRole('button', { name: `Ouvrir ${cible.reference}` }))
    await waitFor(() => expect(defile.mock.contexts.at(-1)).toBe(document.getElementById(`devis-row-${cible.id}`)))
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

// ADEV34 — la date proposée par la modale est la date LOCALE (Africa/Casablanca),
// bornée à aujourd'hui : à 00:30 au Maroc (23:30 UTC la veille) elle vaut déjà
// le lendemain UTC. Le refus serveur d'une date future (400 nommant
// `date_acceptation`) est affiché depuis le CORPS de la réponse.
describe("ADEV34 — date d'acceptation locale", () => {
  // La date « locale » est celle du fuseau du processus : on le FIXE à
  // Africa/Casablanca (UTC+1 en octobre) pour que le test soit le même sur un
  // poste marocain et sur la CI en UTC.
  let tzAvant
  beforeAll(() => {
    tzAvant = process.env.TZ
    process.env.TZ = 'Africa/Casablanca'
  })
  afterAll(() => {
    if (tzAvant === undefined) delete process.env.TZ
    else process.env.TZ = tzAvant
  })
  afterEach(() => { vi.useRealTimers() })

  it("à 23:30 UTC la veille : champ = date locale du jour, max = aujourd'hui", () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-07T23:30:00Z'))
    ouvrir('admin')
    const champ = screen.getByLabelText("Date d'acceptation")
    expect(champ.value).toBe('2026-10-08')
    expect(champ.getAttribute('max')).toBe('2026-10-08')
  })

  it('400 date_acceptation future : le message du corps est affiché', async () => {
    const message = "La date d'acceptation ne peut pas être dans le futur."
    const erreur = vi.spyOn(toast, 'error')
    ventesApi.accepterDevis.mockRejectedValueOnce(Object.assign(new Error('400'), {
      response: { status: 400, data: { date_acceptation: [message] } },
    }))
    const user = userEvent.setup()
    ouvrir('admin')
    await user.type(await screen.findByLabelText('Nom de la personne qui accepte'), 'Sami')
    await user.click(screen.getByRole('button', { name: /Confirmer l'acceptation/ }))
    await waitFor(() => expect(erreur).toHaveBeenCalledWith(message))
    erreur.mockRestore()
  })
})
