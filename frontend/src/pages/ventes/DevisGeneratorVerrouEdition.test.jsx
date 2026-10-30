// QJR549 (contrat QJR503, devis_verrou_edition.json) — l'Édition complète
// envoie son jeton de fraîcheur (`expected_updated_at`), le RÉ-ARME après
// chaque écriture de l'écran (ici : une taille d'offre appliquée) et, sur un
// 409 `devis_modifie`, affiche « Modifié par X » sans rien écrire d'autre.
// L'écran RÉEL est rendu ; seul <DevisOffresTailles> est remplacé par un
// bouton qui signale une écriture (`onDevisEcrit`) — son comportement réseau
// est couvert par DevisOffresTailles.test.jsx.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorVerrouEdition.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('./DevisOffresTailles', () => ({
  default: ({ onDevisEcrit }) => (
    <button type="button" data-testid="stub-ecrit-taille"
            onClick={() => onDevisEcrit && onDevisEcrit('2026-09-30T09:15:00.000000+01:00')}>
      Taille écrite (stub)
    </button>
  ),
}))
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiAvecLead())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancEdition, devisResidentielRouvert } from './devisGenerator.testHelpers.jsx'


const JETON_CHARGEMENT = '2026-09-30T08:41:12.345678+01:00'
const CONFLIT = exempleContrat('ventes', 'devis_verrou_edition', 'exemple_409')

const devisRouvert = (variante) => devisResidentielRouvert(variante, { updated_at: JETON_CHARGEMENT })

const { renderEdition } = bancEdition({ DevisGenerator, stockApi, crmApi, ventesApi })

describe('QJR549 — verrou optimiste de l’Édition complète', () => {
  it('409 devis_modifie → bannière « Modifié par … », rien d’autre écrit', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.replaceLignesDevis.mockRejectedValue({ response: { status: 409, data: CONFLIT } })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    const banniere = await screen.findByTestId('devis-verrou-banner')
    expect(banniere.textContent).toMatch(new RegExp(`Modifié par ${CONFLIT.updated_by_nom}`))
    const [, , extra] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(extra.expected_updated_at).toBe(JETON_CHARGEMENT)
    expect(ventesApi.patchEtudeParams).not.toHaveBeenCalled()
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
    expect(screen.queryByText('APRES-ENREGISTREMENT')).toBeNull()
  })

  it('« Enregistrer quand même » renvoie UNE fois sans jeton', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.replaceLignesDevis
      .mockRejectedValueOnce({ response: { status: 409, data: CONFLIT } })
      .mockResolvedValueOnce({ data: { updated_at: '2026-09-30T10:00:00+01:00' } })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await screen.findByTestId('devis-verrou-banner')
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer quand même/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(2))
    const [, , extra] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(extra).not.toHaveProperty('expected_updated_at')
  })

  // ERR-AGNR-VERROU-DEVIS-NEUF — le re-envoi d'un enregistrement dont la
  // réponse s'est perdue tombe sur le 1er encore en cours (409 « en cours ») :
  // l'écran réessaie SEUL le MÊME corps (même jeton) et reçoit la réponse
  // rejouée — ni bannière « Modifié par », ni erreur.
  it('409 « en cours » sur replace-lines : reprise du même corps, aucune bannière', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    const EN_COURS = Object.assign(new Error('Request failed with status code 409'), {
      response: { status: 409, data: { code: 'idempotency_en_cours', detail: 'Une requête identique est déjà en cours de traitement.' } },
    })
    ventesApi.replaceLignesDevis
      .mockRejectedValueOnce(EN_COURS)
      .mockResolvedValueOnce({ data: { updated_at: '2026-09-30T10:00:00+01:00' } })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(2), { timeout: 10000 })
    const [premier, second] = ventesApi.replaceLignesDevis.mock.calls
    expect(second).toEqual(premier)
    expect(second[2].expected_updated_at).toBe(JETON_CHARGEMENT)
    expect(screen.queryByTestId('devis-verrou-banner')).toBeNull()
    expect(screen.queryByTestId('erreur-enregistrement')).toBeNull()
  }, 20000)

  it('après une écriture de l’écran (taille appliquée), la sauvegarde envoie le NOUVEAU jeton', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByTestId('stub-ecrit-taille'))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , extra] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(extra.expected_updated_at).toBe('2026-09-30T09:15:00.000000+01:00')
    expect(extra.expected_updated_at).not.toBe(JETON_CHARGEMENT)
  })
})
